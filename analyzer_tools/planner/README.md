# Experiment planning tool

# TODO: add nested sampler
In some cases the information gain can be comparable in different scenarios.
For instance in the case of a CuOx layer on top of copper, both a protiated and 
deuterated electrolyte will lead to similar information gains. But the protiated 
electrolyte model looks very close to a simpler model without an oxide, as the
oxide is lost in the roughness. Using a nested sampler to compare two models (with and without an oxide) might give us better insight into what deuteration ratio is best.

We could do this by adding an alternate model to the experiment planner.