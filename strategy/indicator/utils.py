# @date 2018-09-02
# @author Frederic Scherma, All rights reserved without prejudices.
# @author Xavier BONNIN
# @license Copyright (c) 2018 Dream Overflow
# Indicator utils

import numpy as np
import scipy.signal as signal


def down_sample(data, factor, n=4, ftype='iir'):
    return signal.decimate(data, factor, n, ftype)

def MM_n(N, data):
    """
    Calcul de la moyenne mobile sur N points.
    """
    out = np.zeros(len(data))

    for j in range(N):
        out[j] = np.average(data[:j+1])
    for (j,d) in enumerate(data[N-1:]):
        out[j+N-1] = np.average(data[j:j+N])

    return out


def MMexp_n(N, data, has_previous_val = False, previous_value = 0):
    """
    Calcul de la moyenne mobile exponentielle sur N periodes
    previous_val permet d'initialiser la 1ere valeur correctement
    Si la valeur n'est pas initialisee (False, par defaut), la fonction calcule la moyenne mobile avec 
    n=1, 2, 3, ..., N pour les N premiers echantillons
    """
    An = 2.0 / (1.0 + N)
    out = np.zeros(len(data))

    if (has_previous_val):
        out[0] = data[0]*An + (1-An)*previous_value 
        for (j,d) in enumerate(data[1:]):
            out[j+1] = d*An + (1-An)*out[j]
    else:
        for j in range(N):
            out[j] = np.average(data[:j+1])
        for (j,d) in enumerate(data[N-1:]):
            out[j+N-1] = d*An + (1-An)*out[j+N-2]

    return out


def trend(data):
    """
    Calcul de la pente.
    """
    argmin = np.argmin(data)
    argmax = np.argmax(data)

    divider = (data[argmax] + data[argmin])

    if divider == 0.0:
        return 0.0

    if argmin < argmax:
        return (data[argmax] - data[argmin]) / (data[argmax] + data[argmin])
    elif argmin > argmax:
        return (data[argmin] - data[argmax]) / (data[argmin] + data[argmax])

    return  0.0


def trend_extremum(data):
    """
    Calcul de la pente en prenant les extremes (premiers et derniers elements)
    """
    if data[0] < data[-1]:
        argmin = data[0]
        argmax = data[-1]

        if argmax + argmin:
            return (argmax - argmin) / (argmax + argmin)

    elif data[0] > data[-1]:
        argmin = data[-1]
        argmax = data[0]

        if argmax + argmin:
            return (argmin - argmax) / (argmax + argmin)

    return 0.0


def cross(p, n):
    """
    Check of two lines cross from previous and new data couples.

    @param p couple with the previous two values
    @param n couple with the last two values

    @return 0 if no cross, 1 if first cross up second, -1 for down.
    """
    # return (p[0] > p[1] and n[0] < n[1]) or (p[0] < p[1] and n[0] > n[1])
    if (p[0] > p[1] and n[0] < n[1]):
        return -1
    elif (p[0] < p[1] and n[0] > n[1]):
        return 1

    return 0


def crossover(x, y):
    """
    Last two values of X serie cross over Y serie.
    """
    return x[-1] > y[-1] and x[-2] < y[-2]


def crossunder(x, y):
    """
    Last two values of X serie under over Y serie.
    """
    return x[-1] < y[-1] and x[-2] > y[-2]


def divergence(a, b):
    """
    Check if sign(a) != sign(b)
    """
    return np.sign(a) != np.sign(b) and a != 0 and b != 0


def average(data):
    """
    Return the average of the array of float.
    """
    return np.average(data)
