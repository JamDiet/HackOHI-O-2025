import numpy as np
import json
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
    
    def close(self):
        if self.socket:
            self.socket.close()

# Usage
simulator = UnitySimulator()
simulator.connect()

for generation in range(100):
    passenger_sequence = np.random.permutation(150)
    boarding_time = simulator.simulate(passenger_sequence)
    print(f"Generation {generation}: Time = {boarding_time}")

simulator.close()


def order_by_weights(weight_arr: np.ndarray):
    '''
    Order passenger seat numbers by the weight attributed to each seat.
    '''
    return np.argsort(weight_arr) + np.ones(weight_arr.shape)


def call_to_unity(passenger_sequence: np.ndarray, socket):
    json_sequence = json.dumps(passenger_sequence.tolist()).encode('utf-8')
    # TODO - Interface with Jonah's code, return total time and individual passenger times


def objective(weight_arr: np.ndarray):
    '''
    Objective function for SciPy differential evolution
    '''
    passenger_sequence = order_by_weights(weight_arr)
    total_time, passenger_times = call_to_unity(passenger_sequence)
    return total_time + np.std(passenger_times)


def optimize(num_passengers: int):
    x0 = np.array(range(1, num_passengers+1)) / float(num_passengers)
    bounds = np.array([(0., 1.) for _ in range(num_passengers)])

    res = differential_evolution(func=objective, bounds=bounds, x0=x0)

    return order_by_weights(res.x)