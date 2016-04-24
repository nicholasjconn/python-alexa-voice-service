
import json

def write_dict(path, in_dict):
    """ Write a dictionary to a file using JSON. The dictionary must only contain
        values that are JSON serializable.

    :param path: complete path including file name for output file
    :param in_dict: input dictionary to save
    """
    with open(path, 'w') as file:
        json.dump(in_dict, file)


def read_dict(path):
    """ Reads a dictionary from a file using JSON. This file should have been
        written by write_dict.

    :param path: complete path including file name for output file
    :return: output dictionary from file
    """
    with open(path) as file:
        out_dict = json.load(file)
    return out_dict
