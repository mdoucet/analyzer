from refl1d.names import *


def create_fit_experiment(q, dq, data, errors):
    # Go from FWHM to sigma
    dq /= 2.355

    # The QProbe object represents the beam
    probe = QProbe(q, dq, R=data, dR=errors)
    probe.intensity = Parameter(value=1, name="intensity")

    THF = SLD("THF", rho=5.8)
    Si = SLD("Si", rho=2.07)
    Ti = SLD("Ti", rho=-1.2)
    Cu = SLD("Cu", rho=6.25)
    material = SLD(name="material", rho=5, irho=0.0)

    sample = THF(0, 11.4) | material(30, 13) | Cu(505, 4.6) | Ti(39.5, 9.1) | Si

    M = Experiment(sample=sample, probe=probe, step_interfaces=True)

    sample["Cu"].thickness.range(400.0, 700.0)

    return M
