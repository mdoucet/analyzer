from refl1d.names import *


def create_fit_experiment(q, dq, data, errors):
    # Go from FWHM to sigma
    dq /= 2.355

    # The QProbe object represents the beam
    probe = QProbe(q, dq, R=data, dR=errors)
    probe.intensity = Parameter(value=1, name="intensity")

    H2O = SLD("H2O", rho=-0.56)
    Si = SLD("Si", rho=2.07)
    Ti = SLD("Ti", rho=-2)
    Pt = SLD("Pt", rho=6.36)
    ionomer = SLD(name="ionomer", rho=1, irho=0.0)

    sample = H2O(0, 25) | ionomer(500, 13) | Pt(150, 4.6) | Ti(30, 9.1) | Si

    M = Experiment(sample=sample, probe=probe, step_interfaces=True)

    #sample["H2O"].material.rho.range(4.5, 6.4)
    sample["H2O"].interface.range(1, 45)

    sample["ionomer"].thickness.range(400.0, 700.0)
    sample["ionomer"].material.rho.range(0.0, 4.0)
    sample["ionomer"].interface.range(1.0, 60.0)

    #sample["Pt"].thickness.range(70.0, 200.0)
    #sample["Pt"].material.rho.range(2.0, 12)
    #sample["Pt"].interface.range(1.0, 25.0)

    #sample["Ti"].thickness.range(20.0, 60.0)
    #sample["Ti"].material.rho.range(-3.0, -1)
    #sample["Ti"].interface.range(1.0, 15.0)
    return M
