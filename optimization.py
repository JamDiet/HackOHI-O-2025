from scipy.optimize import differential_evolution
import socket
import json
import numpy as np
import os
from matplotlib import pyplot as plt


class BoardingClass:
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
        self.buffer = b''  # ✅ FIX: bytes, not string
        self.family_loss_history = []
        self.time_history = []
        self.stdev_history = []
        self.loss_history = []
        self.iteration_counter = 0

    # --------------------- CONNECTION HANDLING ---------------------

    def connect(self):
        if self.socket:
            return
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.settimeout(10)
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

    # --------------------- NETWORK IO ---------------------

    def recv_json(self):
        """Read bytes until newline and parse JSON."""
        data = self.buffer
        while not data.endswith(b'\n'):
            chunk = self.socket.recv(4096)
            if not chunk:
                raise ConnectionError("Socket closed before JSON received")
            data += chunk
        line, rest = data.split(b'\n', 1)
        self.buffer = rest
        try:
            return json.loads(line.decode('utf-8'))
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to decode JSON from Unity: {e}")

    def simulate(self, passenger_sequence):
        """Send JSON to Unity and get simulation result."""
        if not self.socket:
            raise ConnectionError("Socket not connected")

        payload = {"passenger_sequence": passenger_sequence.tolist()}
        bytes_out = (json.dumps(payload) + "\n").encode('utf-8')

        try:
            self.socket.sendall(bytes_out)
        except BrokenPipeError as e:
            raise ConnectionError(f"Broken pipe while sending to Unity: {e}")

        resp = self.recv_json()
        if 'time' not in resp:
            raise ValueError("Unity response missing 'time' key")
        if 'time_per_passenger' not in resp:
            resp['time_per_passenger'] = []

        # print("Unity response:", resp)
        return resp

    # --------------------- OPTIMIZATION ---------------------

    def objective(self, weight_arr: np.ndarray):
        """Objective function for DE optimizer."""
        if self.current_class is None:
            raise RuntimeError("current_class not set")

        weight_arr = np.asarray(weight_arr)
        if weight_arr.shape[0] != self.current_class.shape[0]:
            raise ValueError("weight_arr length doesn't match current_class length")

        passenger_sequence = order_by_weights(self.current_class, weight_arr)

        # Initialize family loss
        family_loss = 0.0
        if self.family_indcs is not None:
            fams = self.family_indcs
            if isinstance(fams, np.ndarray) and fams.ndim == 1:
                fams = [fams]
            elif not isinstance(fams, (list, tuple)):
                fams = []

            for family in fams:
                family = np.asarray(family)
                if family.size == 0:
                    continue
                positions = np.where(np.isin(passenger_sequence, family))[0]
                if positions.size == 0:
                    continue
                mean_idx = np.mean(positions)
                family_loss += np.mean(np.abs(positions - mean_idx))

        # Call Unity
        try:
            result = self.simulate(passenger_sequence)
        except ConnectionError as e:
            print("Unity connection error in objective:", e)
            return np.inf
        except Exception as e:
            print("Unexpected error while simulating:", e)
            return np.inf

        sim_time = float(result.get('time', 0.0))
        per_pass = result.get('time_per_passenger', [])
        extra = float(np.std(per_pass)) if len(per_pass) > 0 else 0.0

        loss = family_loss + sim_time + extra
        # print(f"loss components: family_penalty={family_loss:.4f}, sim_time={sim_time:.4f}, std={extra:.4f} -> total={loss:.4f}")
        return loss

    def callback(self, xk, convergence):
        """Callback called every DE iteration."""
        weight_arr = np.asarray(xk)
        passenger_sequence = order_by_weights(self.current_class, weight_arr)

        family_loss = 0.0
        if self.family_indcs is not None:
            fams = self.family_indcs
            if isinstance(fams, np.ndarray) and fams.ndim == 1:
                fams = [fams]
            elif not isinstance(fams, (list, tuple)):
                fams = []

            for family in fams:
                family = np.asarray(family)
                if family.size == 0:
                    continue
                positions = np.where(np.isin(passenger_sequence, family))[0]
                if positions.size == 0:
                    continue
                mean_idx = np.mean(positions)
                family_loss += np.mean(np.abs(positions - mean_idx))

        try:
            result = self.simulate(passenger_sequence)
        except Exception as e:
            print("Error during callback simulate:", e)
            return np.inf

        sim_time = float(result.get('time', 0.0))
        per_pass = result.get('time_per_passenger', [])
        extra = float(np.std(per_pass)) if len(per_pass) > 0 else 0.0

        loss = family_loss + sim_time + extra
        print(f'Iteration {self.iteration_counter}: fitness={loss:.4f}')

        # Update history
        self.family_loss_history.append(family_loss)
        self.time_history.append(sim_time)
        self.stdev_history.append(extra)
        self.loss_history.append(loss)
        self.iteration_counter += 1
        return False  # continue optimization

    def run_optimizer_on_class(self, class_data):
        """Run optimizer for a single class."""
        class_id, data = class_data
        num_passengers = data.indices.shape[0]
        self.current_class = data.indices
        self.family_indcs = data.families

        bounds = [(0.0, 1.0)] * num_passengers

        res = differential_evolution(
            self.objective,
            bounds=bounds,
            maxiter=10,
            workers=1,
            callback=self.callback
        )

        return class_id, res.x, res.fun

    # --------------------- PLOTTING ---------------------

    def plot_results(self, filepath: str):
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        fig, axs = plt.subplots(2, 2, figsize=(10, 6))
        fig.suptitle('Loss Terms per Iteration')

        axs[0, 0].plot(self.loss_history)
        axs[0, 0].set_title('Total Loss')

        axs[0, 1].plot(self.time_history)
        axs[0, 1].set_title('Boarding Time')

        axs[1, 0].plot(self.stdev_history)
        axs[1, 0].set_title('Per Passenger Time StDev')

        axs[1, 1].plot(self.family_loss_history)
        axs[1, 1].set_title('Family Separation')

        fig.tight_layout()
        plt.savefig(filepath)
        plt.close(fig)

        # Reset for next class
        self.family_loss_history.clear()
        self.loss_history.clear()
        self.stdev_history.clear()
        self.time_history.clear()
        self.iteration_counter = 0


def order_by_weights(indices: np.ndarray, weight_arr: np.ndarray):
    """Return seat ids ordered by increasing weight."""
    return indices[np.argsort(weight_arr)]


if __name__ == '__main__':
    simulator = UnitySimulator()
    simulator.connect()

    num_passengers = 30
    seat_num_array = np.arange(1, num_passengers + 1)

    family_1 = np.arange(1, 6)
    family_2 = np.arange(11, 16)
    family_3 = np.arange(21, 26)

    class_1 = np.arange(1, 11)
    class_2 = np.arange(11, 21)
    class_3 = np.arange(21, 31)

    classes = [class_1, class_2, class_3]
    boarding_groups = [BoardingClass(indices=c, families=None) for c in classes]

    boarding_groups[0].families = family_1
    boarding_groups[1].families = family_2
    boarding_groups[2].families = family_3

    class_data = [(i, boarding_groups[i]) for i in range(len(boarding_groups))]

    for cid, data in class_data:
        cid, best_x, best_fun = simulator.run_optimizer_on_class((cid, data))
        print(f"Class {cid}: best fitness {best_fun:.4f}")
        simulator.plot_results(f"data/plots/boarding_group_{cid}.png")
        np.save(f"data/boarding_orders/boarding_group_{cid}.npy", best_x)

    simulator.close()
