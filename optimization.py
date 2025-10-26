from scipy.optimize import differential_evolution
import socket
import json
import numpy as np
from matplotlib import pyplot as plt


class BoardingClass():
    def __init__(self, indices: np.ndarray, families):
        """
        indices: 1D numpy array of seat ids for this boarding class (e.g. [1,2,3...])
        families: either
            - None (no family info),
            - a 1D numpy array of seat ids representing one family,
            - or a list of numpy arrays, each array containing seat ids for one family.
        """
        self.indices = np.asarray(indices)
        self.families = families


class UnitySimulator:
    def __init__(self, host='localhost', port=5555):
        self.host = host
        self.port = port
        self.socket = None
        self.family_indcs = None
        self.current_class = None
        self.buffer = ''
        self.family_loss_history = []
        self.time_history = []
        self.stdev_history = []
        self.loss_history = []
        self.iteration_counter = 0

    def connect(self):
        if self.socket:
            return
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.settimeout(10)  # avoid hanging forever
        self.socket.connect((self.host, self.port))
        print("Connected to Unity simulator")

    def close(self):
        if self.socket:
            try:
                self.socket.close()
            except Exception:
                pass
            self.socket = None
            self.buffer = b''
            print("Socket closed")

    def recv_json(self):
        """
        Read bytes until newline and parse JSON. Raises ConnectionError if connection closed.
        """
        data = self.buffer
        while not data.endswith(b'\n'):
            chunk = self.socket.recv(4096)
            if not chunk:
                # remote closed connection
                raise ConnectionError("Socket closed before JSON received")
            data += chunk
        # split off one line
        line, rest = data.split(b'\n', 1)
        self.buffer = rest
        try:
            return json.loads(line.decode('utf-8'))
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to decode JSON from Unity: {e}")

    def simulate(self, passenger_sequence):
        """
        Send {"passenger_sequence": [...]} and expect a JSON response like:
            {"time": <float>, "time_per_passenger": [..]}
        Returns the parsed dict.
        """
        if not self.socket:
            raise ConnectionError("Socket not connected")
        payload = {"passenger_sequence": passenger_sequence.tolist()}
        bytes_out = (json.dumps(payload) + "\n").encode('utf-8')
        try:
            self.socket.sendall(bytes_out)
        except BrokenPipeError as e:
            raise ConnectionError(f"Broken pipe while sending to Unity: {e}")

        # receive and parse
        resp = self.recv_json()
        # minimal validation
        if 'time' not in resp:
            raise ValueError("Unity response missing 'time' key")
        if 'time_per_passenger' not in resp:
            # make it present (empty) to keep downstream code robust
            resp['time_per_passenger'] = []
        print("Unity response:", resp)
        return resp

    def objective(self, weight_arr: np.ndarray):
        """
        DE objective: takes continuous weights (same length as current_class),
        produces a passenger sequence (ordering of seat ids), sends to Unity,
        and returns a scalar loss.
        """
        # ensure correct shapes
        if self.current_class is None:
            raise RuntimeError("current_class not set")

        weight_arr = np.asarray(weight_arr)
        if weight_arr.shape[0] != self.current_class.shape[0]:
            raise ValueError("weight_arr length doesn't match current_class length")

        # order seats by ascending weight
        passenger_sequence = order_by_weights(self.current_class, weight_arr)

        # family penalty: flexible handling of family_indcs shape
        if self.family_indcs is not None:
            # normalize family representation to list of arrays
            fams = self.family_indcs
            if isinstance(fams, np.ndarray) and fams.ndim == 1:
                fams = [fams]                # one family
            elif isinstance(fams, (list, tuple)):
                # assume already list of arrays
                pass
            else:
                # unknown type; skip penalty
                fams = []

            for family in fams:
                family = np.asarray(family)
                if family.size == 0:
                    continue
                # indices in passenger_sequence where members of `family` appear
                positions = np.where(np.isin(passenger_sequence, family))[0]
                if positions.size == 0:
                    # family seats not present in this class (maybe family spans classes) -> skip
                    continue
                mean_idx = np.mean(positions)
                family_loss = np.mean(np.abs(positions - mean_idx))

        # call Unity
        try:
            result = self.simulate(passenger_sequence)
        except ConnectionError as e:
            print("Unity connection error in objective:", e)
            # return a huge penalty so DE avoids solutions that require simulations when server is down.
            return np.inf
        except Exception as e:
            print("Unexpected error while simulating:", e)
            return np.inf

        # combine simulation time and family penalty
        sim_time = float(result.get('time', 0.))
        per_pass = result.get('time_per_passenger', [])
        extra = 0.0
        try:
            extra = float(np.std(per_pass)) if len(per_pass) > 0 else 0.0
        except Exception:
            extra = 0.0

        loss = family_loss + sim_time + extra
        print(f"loss components: family_penalty={family_loss:.4f}, sim_time={sim_time:.4f}, std={extra:.4f} -> total={loss:.4f}")
        return loss

    def run_optimizer_on_class(self, class_data):
        """Run optimizer for a single class (sequentially)."""
        class_id, data = class_data
        num_passengers = data.indices.shape[0]

        self.current_class = data.indices
        self.family_indcs = data.families

        # bounds as list-of-tuples
        bounds = [(0.0, 1.0)] * num_passengers

        # Initial guess
        x0 = np.zeros_like(data.indices)

        # Differential evolution (single-threaded worker). Remove x0 (not accepted).
        res = differential_evolution(
            self.objective,
            x0=x0,
            bounds=bounds,
            maxiter=1,
            workers=1  # keep single-threaded to avoid parallel calls to Unity
        )

        return class_id, res.x, res.fun
    
    def callback(self, xk, convergence):
        weight_arr = np.asarray(xk)

        # order seats by ascending weight
        passenger_sequence = order_by_weights(self.current_class, weight_arr)

        # family penalty: flexible handling of family_indcs shape
        if self.family_indcs is not None:
            # normalize family representation to list of arrays
            fams = self.family_indcs
            if isinstance(fams, np.ndarray) and fams.ndim == 1:
                fams = [fams]                # one family
            elif isinstance(fams, (list, tuple)):
                # assume already list of arrays
                pass
            else:
                # unknown type; skip penalty
                fams = []

            for family in fams:
                family = np.asarray(family)
                if family.size == 0:
                    continue
                # indices in passenger_sequence where members of `family` appear
                positions = np.where(np.isin(passenger_sequence, family))[0]
                if positions.size == 0:
                    # family seats not present in this class (maybe family spans classes) -> skip
                    continue
                mean_idx = np.mean(positions)
                family_loss = np.mean(np.abs(positions - mean_idx))

        # call Unity
        try:
            result = self.simulate(passenger_sequence)
        except ConnectionError as e:
            print("Unity connection error in objective:", e)
            # return a huge penalty so DE avoids solutions that require simulations when server is down.
            return np.inf
        except Exception as e:
            print("Unexpected error while simulating:", e)
            return np.inf

        # combine simulation time and family penalty
        sim_time = float(result.get('time', 0.))
        per_pass = result.get('time_per_passenger', [])
        extra = 0.0
        try:
            extra = float(np.std(per_pass)) if len(per_pass) > 0 else 0.0
        except Exception:
            extra = 0.0

        loss = family_loss + sim_time + extra
        print(f'Current fitness: {loss}\n')

        # Track number of iterations elapsed
        self.iteration_counter += 1
        print(f'Iteration number: {self.iteration_counter}\n')

        # Save to loss histories
        self.family_loss_history.append(family_loss)
        self.time_history.append(sim_time)
        self.stdev_history.append(extra)
        self.loss_history.append(loss)
    
    def plot_results(self, filepath: str):
        fig, axs = plt.subplots(2, 2)
        fig.suptitle('Loss Terms per Iteration')

        axs[0, 0].plot(self.loss_history)
        axs[0, 0].set_title('Total Loss')

        axs[0, 1].plot(self.time_history)
        axs[0, 1].set_title('Boarding Time')

        axs[1, 0].plot(self.stdev_history)
        axs[1, 0].set_title('Per Passenger Time StDev')

        axs[1, 1].plot(self.family_loss_history)
        axs[1, 1].set_title('Family separation')

        fig.tight_layout()
        fig.savefig(filepath)

        self.family_loss_history.clear()
        self.loss_history.clear()
        self.stdev_history.clear()
        self.time_history.clear()
        self.iteration_counter = 0


def order_by_weights(indices: np.ndarray, weight_arr: np.ndarray):
    """
    Return the seat ids (from `indices`) ordered by increasing weight.
    Both inputs must have the same length.
    """
    idx_order = np.argsort(weight_arr)
    return indices[idx_order]


if __name__ == '__main__':
    simulator = UnitySimulator()

    # connect once (sequential runs use same socket)
    simulator.connect()

    # Define number of passengers to order
    num_passengers = 30
    seat_num_array = np.arange(1, num_passengers+1)

    # Generate 3 5-person families
    family_1 = np.arange(1, 6)
    family_2 = np.arange(11, 16)
    family_3 = np.arange(21, 26)
    seat_num_array = seat_num_array[~np.isin(np.concatenate((family_1, family_2, family_3)))]

    # Generate 3 random class arrays
    class_1 = np.concatenate((np.random.choice(seat_num_array, 5), family_1))
    seat_num_array = seat_num_array[~np.isin(seat_num_array, class_1)]
    class_2 = np.concatenate((np.random.choice(seat_num_array, 5), family_2))
    class_3 = np.concatenate((seat_num_array[~np.isin(seat_num_array, class_2)], family_3))

    classes = [class_1, class_2, class_3]
    boarding_groups = [BoardingClass(indices=c, families=None) for c in classes]

    # Example: mark each class's family structure.
    # For demo, we make one family per class consisting of seats [1..5] and [11..15]
    boarding_groups[0].families = family_1     # single family in first class
    boarding_groups[1].families = family_2   # single family in second class
    boarding_groups[3].families = family_3

    # prepare input for the optimizer runner
    class_data = [(i, boarding_groups[i]) for i in range(len(boarding_groups))]

    # Run optimizer for each class sequentially (re-uses same simulator/socket)
    for cd in class_data:
        cid, best_x, best_fun = simulator.run_optimizer_on_class(cd)
        print(f"Class {cid}: best fitness {best_fun:.4f}")
        simulator.plot_results(f'data\\plots\\boarding_group_{cid}')
        np.save(f'data\\boarding_orders\\boarding_group_{cid}', best_x)

    simulator.close()