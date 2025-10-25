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
        
    def simulate(self, passenger_sequence):
        # Convert to JSON bytes
        json_data = json.dumps(passenger_sequence.tolist())
        json_bytes = json_data.encode('utf-8')
        
        # Send to Unity
        self.socket.sendall(json_bytes)
        
        # Receive result
        result_bytes = self.socket.recv(4096)
        result = json.loads(result_bytes.decode('utf-8'))
        
        return result['time']

    def objective(self, weight_arr: np.ndarray):
        passenger_sequence = order_by_weights(weight_arr)
        return self.simulate(passenger_sequence)
    
    def close(self):
        if self.socket:
            self.socket.close()


def order_by_weights(weight_arr: np.ndarray):
    '''
    Order passenger seat numbers by the weight attributed to each seat.
    '''
    return np.argsort(weight_arr) + np.ones(weight_arr.shape, dtype=int)


if __name__ == '__main__':
    simulator = UnitySimulator()
    simulator.connect()

    num_passengers = 20
    x0 = np.array(range(1, num_passengers+1)) / num_passengers
    bounds = np.array([(0., 1.) for _ in range(num_passengers)])

    res = differential_evolution(simulator.objective, bounds=bounds, x0=x0)