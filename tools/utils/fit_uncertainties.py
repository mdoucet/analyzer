"""
  Show an uncertainty band for an SLD profile.
  This currently works for inverted geometry and fixed substrate roughness, as it aligns
  the profiles to that point before doing the statistics.
"""
from refl1d import uncertainty as errors
import numpy as np


def get_sld_contour(problem, state, cl=90, npoints=200, trim=1000, portion=.3, index=1, align='auto'):
    points, _logp = state.sample(portion=portion)
    points = points[-trim:-1]
    original = problem.getp()
    _profiles, slabs, Q, residuals = errors.calc_errors(problem, points)
    problem.setp(original)
    
    profiles = errors.align_profiles(_profiles, slabs, align)

    # Group 1 is rho
    # Group 2 is irho
    # Group 3 is rhoM
    contours = []
    for model, group in profiles.items():
        ## Find limits of all profiles
        z = np.hstack([line[0] for line in group])
        zp = np.linspace(np.min(z), np.max(z), npoints)

        # Columns are z, best, low, high
        data, cols = errors._build_profile_matrix(group, index, zp, [cl])
        contours.append(data)
    return contours