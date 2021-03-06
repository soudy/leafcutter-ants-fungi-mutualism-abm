"""
Sobol' (global) sensitivity analysis, based on methods provided by the SA notebook and the article of ten Broeke (2016), using SALib python package
Script to run Sobol' SA and save data
"""
from model import LeafcutterAntsFungiMutualismModel, track_ants, track_leaves, track_ratio_foragers
from model import track_ants_leaves, track_dormant_ants
from mesa.batchrunner import BatchRunner
import pandas as pd
import numpy as np
import os
import sys

import time
import argparse
import multiprocess as mp
from itertools import product

from SALib.sample import saltelli
from SALib.analyze import sobol

if not os.path.exists('data/Sobol'):
    os.makedirs('data/Sobol')
if not os.path.exists('figures/Sobol'):
    os.makedirs('figures/Sobol')

# from https://salib.readthedocs.io/en/latest/basics.html

# define the parameters and ranges in a way that is not confusing; uncomment parameters to include in analysis
problem = {
    'fungus_decay_rate': [float, [0.001, 0.02]],
    'energy_biomass_cvn': [float, [1, 4]],
    'fungus_larvae_cvn': [float, [0.55, 1.25]],
    'caretaker_carrying_amount': [float, [0.5, 1.35]],
    'caretaker_roundtrip_mean': [float, [5, 12]]
}

# SALib's saltelli sampler wants it in another format so here we go
problem_sampler = {
    'num_vars': len(problem),
    'names': [key for key in sorted(problem.keys())],
    'bounds': [problem[key][1] for key in sorted(problem.keys())]
}

# set fixed parameters, eg collect_data = False. this includes all parameters not in problem
fixed_parameters = {'collect_data': False,
                    'width': 50,
                    'height': 50,
                    'num_ants': 50,
                    'num_plants': 64,
                    'pheromone_lifespan': 30,
                    'num_plant_leaves': 100,
                    'initial_foragers_ratio': 0.5,
                    'leaf_regrowth_rate': 0.5,
                    'ant_death_probability': 0.01,
                    'initial_fungus_energy': 50,
                    'fungus_decay_rate': 0.005,
                    'energy_biomass_cvn': 2.0,
                    'fungus_larvae_cvn': 0.9,
                    'energy_per_offspring': 1.0,
                    'fungus_biomass_death_threshold': 5,
                    'max_fitness_queue_size': 10,
                    'caretaker_carrying_amount': 1,
                    'caretaker_roundtrip_mean': 5,
                    'dormant_roundtrip_mean': 60.0,
                    }

# remove problem parameters from dictionary of fixed parameters
for key in problem.keys():
    del fixed_parameters[key]

##### ?????? ######
# The SA notebook does this, which is very different implementation than the example of the read the docs????
repetitions = 10
max_steps = 100
distinct_samples = 10


def fungus_biomass(model):
    return model.fungus.biomass


# , problem_sampler, parameter_setting, fixed_parameters, i):
def run_model(args):

    model, args, problem_sampler, parameter_setting, fixed_parameters, i = args

    # create dictionary containing the variable parameters
    var_param = {}
    for key, val in zip(problem_sampler['names'], parameter_setting):
        # transform into integer if required
        # NOTE this is using global variable problem.. not the best method, so think about fix
        if problem[key][0] == int:
            val = round(val)
        var_param[key] = val

    m = model(**var_param, **fixed_parameters)

    while m.running and m.schedule.steps < args["time_steps"]:
        m.step()

    return m, i


def run_model_parallel(args):
    args, model_reporters = args
    n_cores = args["n_cores"]
    if n_cores is None:
        n_cores = mp.cpu_count()

    # load the sample
    param_values = np.loadtxt('data/Sobol/saltellisample')

    results = np.zeros((len(param_values), len(model_reporters.keys())))

    with mp.Pool(n_cores) as pool:
        for model, ix in pool.imap_unordered(
            run_model,
            [(LeafcutterAntsFungiMutualismModel, args, problem_sampler,
              param_values[i], fixed_parameters, i) for i in range(len(param_values))]
        ):
            results[ix] = np.array([model_reporters[key](model)
                                   for key in sorted(model_reporters.keys())])
            #results[ix] = model.fungus.biomass, track_ants(model), track_ratio_foragers(model), track_leaves(model),

    return results


def main(args):
    args, model_reporters = args
    start = time.time()
    results = run_model_parallel((args, model_reporters))
    end = time.time()

    print(f"Done! Took {end - start}")
    print(f"------ Saving data to {args['output_file']} --------")
    np.savez('data/Sobol/'+args["output_file"], results=results,
             fixed_parameters=fixed_parameters, problem=problem_sampler, model_reporters=model_reporters)


def create_saltelli_sample():
    """ create the parameter values. This needs to be done only once!!! """
    param_values = saltelli.sample(
        problem_sampler, N=512, calc_second_order=False)

    np.savetxt('data/Sobol/saltellisample', param_values)


if __name__ == "__main__":
    argparser = argparse.ArgumentParser(
        description="Leafcutter Ants Fungy Mutualism model runner")

    argparser.add_argument("output_file", type=str,
                           help="location of output file")
    # argparser.add_argument("input_sample", type=str, help="location of saltelli sample")

    # argparser.add_argument("-s", "--saltelli-sample", type=int, default=1024,
    #                        help="length of saltelli sample, preferrably power of 2")
    argparser.add_argument("-t", "--time-steps", type=int, default=1000,
                           help="number of time steps to execute")
    argparser.add_argument("-n", "--n-cores", type=int, default=None,
                           help="number of processes to use in pool")

    args = vars(argparser.parse_args())

    # create the parameter values. This needs to be done only once!!!
    # create_saltelli_sample()
    param_values = np.loadtxt('data/Sobol/saltellisample')
    create_saltelli_sample()

    # set the output variables
    # set the output variables
    model_reporters = {"Ants_Biomass": track_ants,
                       "Fungus_Biomass": fungus_biomass,
                       "Fraction forager ants": track_ratio_foragers,
                       "Available leaves": track_leaves,
                       "Dormant caretakers fraction": track_dormant_ants,
                       "Ants with leaves": track_ants_leaves,
                       #    "Death reason": lambda m: m.death_reason,
                       }

    main((args, model_reporters))
