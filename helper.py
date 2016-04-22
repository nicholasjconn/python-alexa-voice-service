
import json

def write_dict(path, in_dict):
    with open(path, 'w') as file:
        json.dump(in_dict, file)


def read_dict(path):
    with open(path) as file:
        out_dict = json.load(file)
    return out_dict
