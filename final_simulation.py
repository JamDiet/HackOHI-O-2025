from optimization import UnitySimulator
import numpy as np

# Assemble boarding order from optimized sequences
boarding_order = []
for i in range(3):
    boarding_order.append(np.load(f'data/boarding_orders/boarding_group_{i}.npy'))
# boarding_order = np.concatenate(tuple(boarding_order))
print(boarding_order)
# # Run simulation
# simulator = UnitySimulator()
# simulator.connect()
# simulator.simulate(boarding_order)