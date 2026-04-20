# Reflectometry Data Pipeline

## During the Experiment
- Every experiment has a uniquer identifier, which follows the format `IPTS-<N>`, where N is a number.
- Users will align their sample and measure it. At the facility, the raw data goes into a folder named `/SNS/REF_L/IPTS-<N>/nexus`.
- A full reflectometry measurement is often make of several segments, each acquired in a separate configuration of the instrument. This is done by changing the angle of reflection and the wavelength band.
- The raw data is "reduced" from neutron events to R(Q). These are stored in `/SNS/REF_L/IPTS-<N>/shared/autoreduce`. When several runs/segments belong together, a file that combines them is also produced.

## Assessing Data Reduction
- Before moving to analysis, a SME will look at the data reduction and assess its correctness.
- This may be done by looking to artefacts in the data, or by looking at the overlap region between segments. This can point out issues like misalignment.
- Problem with the data reduction can also show up during analysis, so a coarse analysis is usually performed be moving to the full analysis phase.
- When issues are found, the reduction parameters/options may be changed, and the data for a given sample may be re-processed in batch.

## Starting the Analysis process
- Since the reflectivity data is small, it is often copied on the user's system. All the data (partial segments and combined data) are usually in the same folder.
- We will assume that the user will have a markdown file for each sample, describing the sample and how it was measured.
- From the description, we will use AuRE to generate an appropriate refl1d model file.
- The user may load that file in refl1d, or use AuRE for automated fitting.
- We then use AuRE to assess the results and produce a final human-readable output, and a markdown file with fit parameters and plots.

## Analyzer Package Upgrade Project
The original alzyer package dates from last summer, when the coding agents were not as good and agent skills didn't exist. 
We would like to upgrade this package to use a modern approach for Spring 2026. We already started this process, but a lot remains.
Here is a list of updates:

1- **Model creation**: the create_model_script.py and create_temporary_model.py should be 
replaced by a call to AuRE. AuRE is able to generate a refl1d model from a user description of 
the measurement. We should leverage that instead of using heuristics. AuRE will produce a 
refl1d json problem. We will need to add functionality to read this json file and produce a script. Note: AuRE doesn't currently have a CLI for model generation. It's on their TOD list.

2- **Data assessor**: the partial_data_assessor.py needs a refresh. We may want to use LLM calls here too. Read all the skills available to suggest improvements.

3- **Executing fits**: run_fit.py should leverage AuRE. It should perhaps even just return the on-liner to use with AuRE rather than being an interface to it.

4- **Assessing fits**: result_assessor.py should leverage the AuRE CLI for that purpose and augment it's results.

5- **Overall workflow**: We need to define an overall data pipeline/workflow. Although all these steps can be done individually, we really want an orchestrating process to help the user along.
This doesn't have to be a full agentic workflow for now. I don't think we want to use langchain, for instance, in this version. Perhaps in the future.

6- **Agent skills refactor**: We need to assess the agent skills and see if the older ones are covered by the recently created ones. Some of them had specific use-cases in mind, and we may want to consilidate some and split others to address specific concerns.

