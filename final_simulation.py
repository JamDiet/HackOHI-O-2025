from optimization import UnitySimulator, order_by_weights
import numpy as np

# Assemble boarding order from optimized sequences
boarding_order = []
for i in range(3):
    weights = np.load(f'data\\boarding_orders\\boarding_group_{i}')
    boarding_order.append(order_by_weights(np.arange(i*10+1, i*10+11), weights))
boarding_order = np.concatenate(tuple(boarding_order))

# Run simulation
simulator = UnitySimulator()
simulator.connect()
simulator.simulate(boarding_order)