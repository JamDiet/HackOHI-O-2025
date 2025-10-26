from scipy.optimize import differential_evolution
import socket
import json
import numpy as np


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
        self.buffer = b''

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
        loss = 0.0
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
                loss += np.mean(np.abs(positions - mean_idx))

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
        sim_time = float(result.get('time', np.inf))
        per_pass = result.get('time_per_passenger', [])
        extra = 0.0
        try:
            extra = float(np.std(per_pass)) if len(per_pass) > 0 else 0.0
        except Exception:
            extra = 0.0

        total_loss = loss + sim_time + extra
        print(f"loss components: family_penalty={loss:.4f}, sim_time={sim_time:.4f}, std={extra:.4f} -> total={total_loss:.4f}")
        return total_loss

    def run_optimizer_on_class(self, class_data):
        """Run optimizer for a single class (sequentially)."""
        class_id, data = class_data
        num_passengers = data.indices.shape[0]

        self.current_class = data.indices
        self.family_indcs = data.families

        # bounds as list-of-tuples
        bounds = [(0.0, 1.0)] * num_passengers

        # Differential evolution (single-threaded worker). Remove x0 (not accepted).
        res = differential_evolution(
            self.objective,
            bounds=bounds,
            maxiter=1,
            workers=1  # keep single-threaded to avoid parallel calls to Unity
        )

        return class_id, res.x, res.fun


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

    # create classes: here using 1-based seat ids (1..10 and 11..20)
    classes = [np.arange(1, 11), np.arange(11, 21)]
    boarding_groups = [BoardingClass(indices=c, families=None) for c in classes]

    # Example: mark each class's family structure.
    # For demo, we make one family per class consisting of seats [1..5] and [11..15]
    boarding_groups[0].families = [np.arange(1, 6)]     # single family in first class
    boarding_groups[1].families = [np.arange(11, 16)]   # single family in second class

    # prepare input for the optimizer runner
    class_data = [(i, boarding_groups[i]) for i in range(len(boarding_groups))]

    # Run optimizer for each class sequentially (re-uses same simulator/socket)
    results = []
    for cd in class_data:
        cid, best_x, best_fun = simulator.run_optimizer_on_class(cd)
        print(f"Class {cid}: best fitness {best_fun:.4f}")
        results.append((cid, best_x, best_fun))

    simulator.close()
