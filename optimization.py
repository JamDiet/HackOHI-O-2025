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
        # Send with newline
        json_data = json.dumps(passenger_sequence.tolist()) + "\n"
        self.socket.sendall(json_data.encode('utf-8'))
        
        # Receive until newline
        while '\n' not in self.buffer:
            chunk = self.socket.recv(4096).decode('utf-8')
            if not chunk:
                raise ConnectionError("Connection closed")
            self.buffer += chunk
        
        # Extract one complete message
        message, self.buffer = self.buffer.split('\n', 1)
        
        return json.loads(message)

    def objective(self, weight_arr: np.ndarray):
        # Convert weight array into int array of passenger numbers
        passenger_sequence = order_by_weights(weight_arr)

        # Get simulation results and return losses
        loss_dict =  self.simulate(passenger_sequence)
        return loss_dict['time'] + np.std(loss_dict['time_per_passenger'])
    
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