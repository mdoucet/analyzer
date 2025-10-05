from refl1d.names import *


def create_fit_experiment(q, dq, data, errors):
    # Go from FWHM to sigma
    dq /= 2.355

    # The QProbe object represents the beam
    probe = QProbe(q, dq, R=data, dR=errors)
    probe.intensity = Parameter(value=1, name="intensity")
    #probe.intensity.pm(0.05)

    THF = SLD("THF", rho=5.8)
    Si = SLD("Si", rho=2.07)
    Ti = SLD("Ti", rho=-1.2)
    Cu = SLD("Cu", rho=6.5)
    material = SLD(name="material", rho=3.5, irho=0.0)

    sample = THF(0, 11.4) | material(50, 13) | Cu(505, 4.6) | Ti(39.5, 9.1) | Si

    M = Experiment(sample=sample, probe=probe, step_interfaces=True)

    #sample["THF"].material.rho.range(4.5, 6.4)
    sample["THF"].interface.range(1, 15)

    #sample["Ti"].thickness.range(30.0, 60.0)
    #sample["Ti"].material.rho.range(-3.0, -1)
    #sample["Ti"].interface.range(1.0, 22.0)

    sample["material"].thickness.range(10.0, 85.0)
    sample["material"].material.rho.range(3.0, 6.0)
    sample["material"].interface.range(1.0, 15.0)

    sample["Cu"].thickness.range(400.0, 700.0)
    #sample["Cu"].material.rho.range(2.0, 12)
    #sample["Cu"].interface.range(1.0, 12.0)

    return M
