from scipy.optimize import differential_evolution
import socket
import json
import numpy as np

class UnitySimulator:
    def __init__(self, host='localhost', port=5555):
        self.host = host
        self.port = port
        self.socket = None
        
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
        try:
            passenger_sequence = order_by_weights(weight_arr)
            return self.simulate(passenger_sequence)
        except Exception as e:
            print("Objective error:", e)
            return np.inf
    
    def close(self):
        if self.socket:
            self.socket.close()


def order_by_weights(weight_arr: np.ndarray):
    '''
    Order passenger seat numbers by the weight attributed to each seat.
    '''
    return np.argsort(weight_arr) + np.ones(weight_arr.shape, dtype=int)


if __name__ == '__main__':
    # Initialize simulator
    simulator = UnitySimulator()
    simulator.connect()

    # Establish optimization conditions
    num_passengers = 20
    x0 = np.array(range(1, num_passengers+1)) / num_passengers
    bounds = np.array([(0., 1.) for _ in range(num_passengers)])
    maxiter = 10

    # Optimize and print best results
    res = differential_evolution(simulator.objective, bounds=bounds, x0=x0, maxiter=maxiter)
    print(order_by_weights(res.x))