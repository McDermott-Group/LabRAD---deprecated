# Probe a resonator driven by switching JPM with a HEMT.

import os
import numpy as np

from labrad.units import (us, ns, V, GHz, MHz, rad, dB, dBm,
                          DACUnits, PreAmpTimeCounts)

import adc_qubit_experiments

                          
comp_name = os.environ['COMPUTERNAME'].lower()
Resources = [ {
                'Interface': 'GHz FPGA Boards',
                'Boards': [
                            'Leiden Board DAC 3', 
                            'Leiden Board DAC 4',
                            'Leiden Board ADC 5'
                          ],
                'Leiden Board DAC 3':  {
                                        'DAC A': 'JPM Fast Pulse',
                                        'DAC B': 'None',
                                        'FO1 FastBias Firmware Version': '2.1',
                                        'FO2 FastBias Firmware Version': '2.1',
                                        'Data': False,
                                       },
                'Leiden Board DAC 4': {
                                        'DAC A': 'None',
                                        'DAC B': 'None',
                                        'Data': False,
                                       },
                'Leiden Board ADC 5': {
                                        'RunMode': 'demodulate', #'average'
                                        'FilterType': 'square',
                                        'FilterWidth': 9500 * ns,
                                        'FilterStartAt': 0 * ns,
                                        'FilterLength': 10000 * ns,
                                        'FilterStretchAt': 0 * ns,
                                        'FilterStretchLen': 0 * ns,
                                        'DemodPhase': 0 * rad,
                                        'DemodCosAmp': 255,
                                        'DemodSinAmp': 255,
                                        'DemodFreq': -30 * MHz,
                                        'ADCDelay': 0 * ns,
                                        'Data': True
                                       },
                'Variables': {
                                'Init Time': {},
                                'Bias Time': {},
                                'Measure Time': {},
                                'Bias Voltage': {},
                                'Fast Pulse Time': {},
                                'Fast Pulse Amplitude': {},
                                'Fast Pulse Width': {'Value': 0 * ns},
                                'RF SB Frequency': {'Value': 30 * MHz},
                                'ADC Wait Time': {'Value': 0 * ns}
                             }
                },
                { # GPIB RF Generator.
                    'Interface': 'RF Generator',
                    'Address': comp_name + ' GPIB Bus - GPIB0::20::INSTR',
                    'Variables': {
                                    'RF Power': {'Setting': 'Power'}, 
                                    'RF Frequency': {'Setting': 'Frequency'}
                                 }
                },
                { # Lab Brick Attenuator
                    'Interface': 'Lab Brick Attenuator',
                    'Serial Number': 7032,
                    'Variables': ['RF Attenuation']
                },
                # { # SIM Voltage Source.
                    # 'Interface': 'SIM928 Voltage Source',
                    # 'Address': ('SIM900 - ' + comp_name + 
                                # ' GPIB Bus - GPIB0::26::INSTR::SIM900::3'),
                    # 'Variables': 'Qubit Flux Bias Voltage'
                # },
                { # Leiden
                    'Interface': 'Leiden',
                    'Variables': {'Temperature': {'Setting': 'Mix Temperature'}}
                },
                { # Readings entered manually, software parameters.
                    'Interface': None,
                    'Variables': ['Reps',
                                  'Runs',
                                  'ADC Time'],
                }
            ]

# Experiment Information
ExptInfo = {
            'Device Name': 'LeidenTest',
            'User': 'Ivan Pechenezhskiy',
            'Base Path': r'Z:\mcdermott-group\Data\Matched JPM Photon Counting\Leiden DR 2015-10-02 - Cavity Excitation by JPM',
            'Experiment Name': 'Test',
            'Comments': 'Test.' 
           }
 
# Experiment Variables
ExptVars = {
            'Reps': 500, # should not exceed ~50,000

            'Qubit Flux Bias Voltage': 1.0 * V,

            'RF Frequency': 4.821 * GHz,
            'RF SB Frequency': 30 * MHz,
            'RF Power': -110 * dBm,

            'Init Time': 50 * us,
            'Bias Time': 100 * us,
            'Measure Time': 75 * us,
          
            'Bias Voltage': 0.184 * V,
            'Fast Pulse Time': 10 * ns,
            'Fast Pulse Amplitude': .5 * DACUnits,
            'Fast Pulse Width': 0 * ns,

            'ADC Wait Time': 10 * ns, # time delay between the start of the readout pulse and the start of the demodulation
           }

with adc_qubit_experiments.ADCCavityJPM() as run:
    
    run.set_experiment(ExptInfo, Resources, ExptVars)

    # run.single_shot_iqs(save=False, plot_data=True)
    # run.single_shot_osc(save=False, plot_data=['I', 'Q'])
    # run.avg_osc(save=False, plot_data=['I', 'Q'], runs=250)

    run.sweep('RF Frequency', np.linspace(4.50, 5.00, 11) * GHz, 
                save=True, print_data = ['I', 'Q'], 
                plot_data = ['I', 'Q', 'Mean Absolute Amplitude'], max_data_dim=2, runs=1)