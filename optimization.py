from scipy.optimize import differential_evolution
import socket
import json
import numpy as np
import multiprocessing as mp


class BoardingClass():
    def __init__(self, indices: list, families: list):
        self.indices = indices
        self.families = families
    

class UnitySimulator:
    def __init__(self, host='localhost', port=5555):
        self.host = host
        self.port = port
        self.socket = None
        self.family_indcs = None
        self.current_class = None

    def get_family_indcs(self, num_passengers: int, families: list):
        """
        Place families (groups) into contiguous passenger indices.

        Args:
            num_passengers: total number of seats (indices 0..num_passengers-1)
            families: 1D array-like of family sizes (integers)

        Returns:
            A list of numpy integer arrays; each element contains the contiguous
            seat indices assigned to the corresponding family in the same order
            as `families`.

        Raises:
            ValueError: if sum(families) > num_passengers or any family <= 0.
        """
        families = np.asarray(families, dtype=int)
        if np.any(families <= 0):
            raise ValueError("All family sizes must be positive integers")
        if families.sum() > num_passengers:
            raise ValueError("Not enough seats for all families")

        rng = np.random.default_rng()

        # Try greedy randomized placement with a limited number of attempts.
        max_attempts = 1000
        for attempt in range(max_attempts):
            mask = np.zeros(num_passengers, dtype=bool)
            starts = [None] * len(families)
            order = list(range(len(families)))
            rng.shuffle(order)
            ok = True
            for idx in order:
                f = int(families[idx])
                # find all start positions where f seats are free
                candidates = []
                last_start = num_passengers - f
                for s in range(0, last_start + 1):
                    if not mask[s:s+f].any():
                        candidates.append(s)
                if not candidates:
                    ok = False
                    break
                start = rng.choice(candidates)
                mask[start:start+f] = True
                starts[idx] = start

            if ok:
                # build list of contiguous index arrays in original order
                result = [np.arange(starts[i] + 1, starts[i] + families[i] + 1, dtype=int) for i in range(len(families))]
                self.family_indcs = result
                print(f"Random placement succeeded on attempt {attempt+1}")
                return self.family_indcs

        # If we exhaust attempts, fall back to deterministic packing (left-to-right)
        print("Random placement failed after all attempts, using fallback")
        mask = np.zeros(num_passengers, dtype=bool)
        starts = []
        cur = 0
        for f in families:
            f = int(f)
            if cur + f > num_passengers:
                raise RuntimeError("Failed to place families")
            starts.append(np.arange(cur + 1, cur + f + 1, dtype=int))
            cur += f
        
        self.family_indcs = starts
        
    def connect(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.host, self.port))
        print("Connected to Unity simulator")
    
    def recv_json(self):
        data = b""
        while not data.endswith(b"\n"):
            part = self.socket.recv(4096)
            if not part:
                raise ConnectionError("Socket closed before JSON received")
            data += part
        return json.loads(data.decode('utf-8'))

    def simulate(self, passenger_sequence):
        # Always send newline-terminated JSON
        data = {"passenger_sequence": passenger_sequence.tolist()}
        json_bytes = (json.dumps(data) + "\n").encode('utf-8')
        self.socket.sendall(json_bytes)

        # Receive JSON from Unity
        result = self.recv_json()
        print("Finished! Result:", result)

        return float(result['time'])

    def objective(self, weight_arr: np.ndarray):
        # Convert weight array into int array of passenger numbers
        passenger_sequence = order_by_weights(self.current_class, weight_arr)

        loss = 0.

        # Penalize for family members boarding at different times
        for family in self.family_indcs:
            indcs = [i for i, idx in enumerate(passenger_sequence) if idx in family]
            mean_idx = np.mean(indcs)
            loss += np.mean(np.abs(indcs - mean_idx))

        # Get simulation results and return losses
        loss_dict = self.simulate(passenger_sequence)
        loss += loss_dict['time']

        return loss
    
    def close(self):
        if self.socket:
            self.socket.close()

    def run_optimizer_on_class(self,
                            class_data: list):
        """Each process runs its own optimizer"""
        class_id, data = class_data
        num_passengers = data.shape[0]

        self.current_class = data.indices
        self.get_family_indcs(num_passengers, data.families)

        x0 = np.array(range(1, num_passengers+1)) / num_passengers
        bounds = np.array([(0., 1.) for _ in range(num_passengers)])
        
        result = differential_evolution(
            self.objective,
            x0=x0,
            bounds=bounds,
            workers=1,  # Each optimizer uses 1 worker
            maxiter=10
        )
        
        return class_id, result.x, result.fun


def order_by_weights(indices: np.ndarray, weight_arr: np.ndarray):
    '''
    Order passenger seat numbers by the weight attributed to each seat.
    '''
    idx_order =  np.argsort(weight_arr)
    return np.array([indices[i] for i in idx_order])


if __name__ == '__main__':
    # Initialize simulator
    simulator = UnitySimulator()
    simulator.connect()

    # Establish optimization conditions
    num_passengers = 20

    # Establish classes and which seats
    classes = [np.arange(1, 11), np.arange(11, 21)]
    boarding_groups = [BoardingClass(c, [5]) for c in classes]
    class_data = [(i, c) for i, c in enumerate(boarding_groups)]

    # with mp.Pool(processes=len(classes)) as pool:
    #     results = pool.map(simulator.run_optimizer_on_class, class_data)

    # # Optimize and print best results
    # order = []
    # for c in classes:
    #     simulator.current_class = c
    #     x0 = np.array(range(1, c.shape[0]+1)) / c.shape[0]
    #     bounds = np.array([(0., 1.) for _ in range(c.shape[0])])

    #     # Establish families and family indices
    #     families = [5]
    #     simulator.get_family_indcs(c.shape[0], families)

    #     res = differential_evolution(simulator.objective, bounds=bounds, x0=x0, maxiter=maxiter)
    #     order.append(order_by_weights(c, res.x))