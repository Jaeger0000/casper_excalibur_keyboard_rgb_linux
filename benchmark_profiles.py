import timeit

setup_code = """
data = {"profiles": {"A": 1, "B": 2, "C": 3}}
"""

test_default_dict = """
for k, v in data.get("profiles", {}).items():
    pass
"""

test_or_dict = """
for k, v in (data.get("profiles") or {}).items():
    pass
"""

print("With default dict allocation (existing key):")
print(timeit.timeit(test_default_dict, setup=setup_code, number=10000000))

print("With 'or {}' lazy evaluation (existing key):")
print(timeit.timeit(test_or_dict, setup=setup_code, number=10000000))

setup_code_empty = """
data = {}
"""

test_default_dict_empty = """
for k, v in data.get("profiles", {}).items():
    pass
"""

test_or_dict_empty = """
for k, v in (data.get("profiles") or {}).items():
    pass
"""

print("With default dict allocation (missing key):")
print(timeit.timeit(test_default_dict_empty, setup=setup_code_empty, number=10000000))

print("With 'or {}' lazy evaluation (missing key):")
print(timeit.timeit(test_or_dict_empty, setup=setup_code_empty, number=10000000))
