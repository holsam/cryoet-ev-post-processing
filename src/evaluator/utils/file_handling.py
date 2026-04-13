'''
Utility Functions: generic file handling
'''

# -- Define flattenToml function -----------------
def flattenToml(d: dict, prefix: str="") -> dict:
    '''
    TODO
    '''
    out = {}
    for k,v in d.items():
        full_key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out.update(flattenToml(v, full_key))
        else:
            out[full_key] = v
    return out