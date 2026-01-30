#!/usr/bin/python3

import collections
import copy
import functools
from datetime import datetime, date, timedelta, timezone
from fnmatch import fnmatch
from functools import reduce, partial
import hashlib
import os
import re
import json
import sys
import time
import uuid


class BaseBaseString(type):
    def __instancecheck__(cls, instance):
        return isinstance(instance, (bytes, str))

    def __subclasshook__(cls, thing):
        # TODO: What should go here?
        raise NotImplemented


def with_metaclass(meta, *bases):
    class metaclass(meta):
        __call__ = type.__call__
        __init__ = type.__init__

        def __new__(cls, name, this_bases, d):
            if this_bases is None:
                return type.__new__(cls, name, (), d)
            return meta(name, bases, d)

    return metaclass("temporary_class", None, {})


class basestring(with_metaclass(BaseBaseString)):
    pass


def _recursive_repr(item):
    """Hack around python `repr` to deterministically represent dictionaries.
    This is able to represent more things than json.dumps, since it does not require things to be JSON serializable
    (e.g. datetimes).
    """

    if isinstance(item, basestring):
        result = str(item)

    elif isinstance(item, list):
        result = "[{}]".format(", ".join([_recursive_repr(x) for x in item]))

    elif isinstance(item, (dict, AD, CAD)):
        kv_pairs = [
            "{}: {}".format(_recursive_repr(k), _recursive_repr(item[k])) for k in sorted(item)
        ]
        result = "{" + ", ".join(kv_pairs) + "}"
    else:
        result = repr(item)
    return result


def get_hash(item):
    repr_ = _recursive_repr(item).encode("utf-8")
    return hashlib.md5(repr_).hexdigest()


def get_hash_int(item):
    return int(get_hash(item), base=16)


def escape_chars(text, chars):
    """Helper function to escape uncomfortable characters."""
    text = str(text)
    chars = list(set(chars))

    if "\\" in chars:
        chars.remove("\\")
        chars.insert(0, "\\")

    for ch in chars:
        text = text.replace(ch, "\\" + ch)

    return text


class JSONEncoder(json.JSONEncoder):
    """JSONEncoder to handle ``datetime`` and other problematic object values"""

    class EncodeError(Exception):
        """Raised when an error occurs during encoding"""

    def default(self, obj):
        try:
            if isinstance(obj, (datetime)):
                return obj.timestamp()
            elif isinstance(obj, bytes):
                return self.default(obj.decode("utf-8"))
            elif isinstance(obj, list):
                return [json.JSONEncoder.default(self, x) for x in obj]
            elif isinstance(obj, tuple):
                return tuple([json.JSONEncoder.default(self, x) for x in obj])
            elif hasattr(obj, "toJSON"):
                return obj.toJSON()
            elif hasattr(obj, "jstr"):
                return obj.jstr()
            else:
                try:
                    encoded_obj = json.JSONEncoder.default(self, obj)
                except Exception:
                    encoded_obj = _recursive_repr(obj)
                return encoded_obj
        except Exception:
            return _recursive_repr(obj)


### json object serializer
def json_safe(obj):
    """JSON dumper for objects not serializable by default json code"""
    return json.dumps(
        obj, cls=JSONEncoder, default=str, indent=4, separators=(",", ": "), sort_keys=True
    )


########################################################################################################
# AD - Persistent Attribute Accessible Dict Class
########################################################################################################


class Attribute_Dict_Exception(Exception):
    def __init__(self, message, payload=None):
        Exception.__init__(self)
        self.message = message
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv["message"] = self.message
        return rv


class Attribute_Dict_Error(Attribute_Dict_Exception):
    def __init__(self, message, payload=None):
        Attribute_Dict_Exception.__init__(self, message, payload)


########################################################################################################
# AD - nesting utility functions
########################################################################################################


def __deep_keys(d):
    """Recursive key iterator"""

    def _dkeys(dk):
        """Interior recursion function"""
        dkvs = []
        if not hasattr(dk, "items"):
            return dkvs
        for _k, _v in dict.items(dk):
            if _k == "__dict__":
                dkvs.append(_k)
            if isinstance(_k, bytes):
                _k = _k.decode()
            else:
                _k = str(_k)
            if hasattr(_v, "items"):
                dkvs.append(_k)
                dkvs.extend([f"{_k}.{str(__K)}" for __K in _dkeys(_v)])
            else:
                dkvs.append(_k)
        return sorted(dkvs)

    if not hasattr(d, "items"):
        raise TypeError(f"Object of type {type(d)} does not support the dictionary protocol")

    kvs = []
    for k, v in dict.items(d):
        if k == "__dict__":
            kvs.append(k)
        if isinstance(k, bytes):
            k = k.decode()
        else:
            k = str(k)
        if hasattr(v, "items"):
            kvs.append(k)
            kvs.extend([f"{k}.{str(_K)}" for _K in _dkeys(v)])
        else:
            kvs.append(k)
    return sorted(kvs)


def __deep_items(d):
    """Recursive key iterator"""

    def _ditems(di):
        """Interior recursion function"""
        dkvts = []
        if not hasattr(di, "items"):
            return dkvts
        for _k, _v in dict.items(di):
            if _k == "__dict__":
                dkvts.append((_k, _v))
            if isinstance(_k, bytes):
                _k = _k.decode()
            else:
                _k = str(_k)
            if hasattr(_v, "items"):
                dkvts.append((_k, _v.__class__()))
                dkvts.extend([(f"{_k}.{str(__K)}", __V) for __K, __V in _ditems(_v)])
            else:
                dkvts.append((_k, _v))
        return sorted(dkvts, key=lambda x: x[0])

    if not hasattr(d, "items"):
        raise TypeError(f"Object of type {type(d)} does not support the dictionary protocol")

    kvts = []
    for k, v in dict.items(d):
        if k == "__dict__":
            kvts.append((k, v))
        if isinstance(k, bytes):
            k = k.decode()
        else:
            k = str(k)
        if hasattr(v, "items"):
            kvts.append((k, v.__class__()))
            kvts.extend([(f"{k}.{str(_K)}", _V) for _K, _V in _ditems(v)])
        else:
            kvts.append((k, v))
    return sorted(kvts, key=lambda x: x[0])


def _to_x(d, tgt=None):
    if isinstance(d, tgt):
        return d
    elif hasattr(d, "items"):
        td = tgt()
        for k, v in d.items():
            if k == "__dict__":
                td[k] = v
            if isinstance(k, bytes):
                k = k.decode()
            else:
                k = str(k)
            td[k] = _to_x(v, tgt=tgt)
        return td
    elif isinstance(d, list) and d.__class__ == "list":
        return [_to_x(v, tgt=tgt) for v in d]
    elif isinstance(d, bytes):
        return d.decode()
    else:
        return d


class AD(dict):
    meta = {}
    consul_value_sig = sorted(
        ["CreateIndex", "ModifyIndex", "LockIndex", "Flags", "Key", "Value", "Session"]
    )

    def __init__(self, *args, **kwargs):
        dict.__init__(self)

        if "persistTGT" in kwargs:
            self.set_file_persistence(kwargs["persistTGT"], flush=kwargs.get("flush"))
            del kwargs["persistTGT"]
            if "flush" in kwargs:
                del kwargs["flush"]

        self.update(*args, **kwargs)

    def __add__(self, tgt):
        tmp = AD(**self)
        tmp.update(tgt)
        return tmp

    def __iadd__(self, tgt):
        self.update(tgt)

    def __cmp__(self, other):
        return id(self) == id(other)

    def __contains__(self, key):
        try:
            if isinstance(key, bytes):
                key = key.decode()
            else:
                key = str(key)
            if "." in key:
                path, key = key.split(".", 1)
                if path in dict.keys(self):
                    return key in dict.__getitem__(self, path)
                else:
                    return False
            else:
                return key in dict.keys(self)
        except Exception:
            return False

    has_key = __contains__

    def __delattr__(self, key):
        try:
            self.__delitem__(key)
        except:
            raise AttributeError(key)

    def __delitem__(self, key):
        try:
            if isinstance(key, bytes):
                key = key.decode()
            else:
                key = str(key)
            if "." in key:
                path, key = key.split(".", 1)
                del dict.__getitem__(self, path)[key]
            else:
                dict.__delitem__(self, key)
        except KeyError:
            pass

    def __deepcopy__(self):
        return AD(AD._deep_items(self))

    copy = __deepcopy__

    def __getattr__(self, key):
        try:
            return self.__getitem__(key)
        except:
            raise AttributeError(key)

    def __getitem__(self, key):
        try:
            if isinstance(key, bytes):
                key = key.decode()
            else:
                key = str(key)
            if "." in key:
                path, key = key.split(".", 1)
                return dict.__getitem__(self, path)[key]
            else:
                return dict.__getitem__(self, key)
        except:
            raise KeyError(key)

    def __hash__(self):
        return id(self)

    def __iter__(self):
        for k in self.keys():
            yield k

    def __setattr__(self, key, value):
        self.__setitem__(key, value)

    def __setitem__(self, key, value):
        if isinstance(key, bytes):
            key = key.decode()
        else:
            key = str(key)
        if "." in key:
            path, key = key.split(".", 1)
            if isinstance(dict.setdefault(self, path, AD()), (AD, dict)):
                if isinstance(dict.__getitem__(self, path), dict):
                    dict.__setitem__(self, path, _to_x(dict.__getitem__(self, path), tgt=AD))
            else:
                dict.__setitem__(self, path, AD())
            dict.__getitem__(self, path).__setitem__(key, value)
        else:
            value = _to_x(value, tgt=AD)
            dict.__setitem__(self, key, value)

    def __setstate__(self, state):
        self.update(state)

    def __myself__(self, me, params=None):
        my_id = id(me)
        if my_id not in AD.meta:
            AD.meta[my_id] = {}
            if params and isinstance(params(dict, AD)):
                AD.meta[my_id].update(params)
        return AD.meta[my_id]

    @staticmethod
    def _deep_items(d):
        """Recursive key iterator"""

        def _ditems(di):
            """Interior recursion function"""
            dkvts = []
            if not hasattr(di, "items"):
                return dkvts
            for _k, _v in dict.items(di):
                if _k == "__dict__":
                    dkvts.append((_k, _v))
                if isinstance(_k, bytes):
                    _k = _k.decode()
                else:
                    _k = str(_k)
                if hasattr(_v, "items"):
                    dkvts.append((_k, AD()))
                    dkvts.extend([(f"{_k}.{str(__K)}", __V) for __K, __V in _ditems(_v)])
                else:
                    dkvts.append((_k, _v))
            return sorted(dkvts, key=lambda x: x[0])

        if not hasattr(d, "items"):
            raise TypeError(f"Object of type {type(d)} does not support the dictionary protocol")

        kvts = []
        for k, v in dict.items(d):
            if k == "__dict__":
                kvts.append((k, v))
            if isinstance(k, bytes):
                k = k.decode()
            else:
                k = str(k)
            if hasattr(v, "items"):
                kvts.append((k, AD()))
                kvts.extend([(f"{k}.{str(_K)}", _V) for _K, _V in _ditems(v)])
            else:
                kvts.append((k, v))
        return sorted(kvts, key=lambda x: x[0])

    @staticmethod
    def _deep_keys(d):
        """Recursive key iterator"""

        def _dkeys(dk):
            """Interior recursion function"""
            dkvs = []
            if not hasattr(dk, "items"):
                return dkvs
            for _k, _v in dict.items(dk):
                if _k == "__dict__":
                    dkvs.append(_k)
                if isinstance(_k, bytes):
                    _k = _k.decode()
                else:
                    _k = str(_k)
                if hasattr(_v, "items"):
                    dkvs.append(_k)
                    dkvs.extend([f"{_k}.{str(__K)}" for __K in _dkeys(_v)])
                else:
                    dkvs.append(_k)
            return sorted(dkvs)

        if not hasattr(d, "items"):
            raise TypeError(f"Object of type {type(d)} does not support the dictionary protocol")

        kvs = []
        for k, v in dict.items(d):
            if k == "__dict__":
                kvs.append(k)
            if isinstance(k, bytes):
                k = k.decode()
            else:
                k = str(k)
            if hasattr(v, "items"):
                kvs.append(k)
                kvs.extend([f"{k}.{str(_K)}" for _K in _dkeys(v)])
            else:
                kvs.append(k)
        return sorted(kvs)

    def _json_safe(self):
        """JSON dumper for objects not serializable by default json code"""
        return json.dumps(
            self, cls=JSONEncoder, default=str, indent=4, separators=(",", ": "), sort_keys=True
        )

    @staticmethod
    def _jvalue(value):
        try:
            if isinstance(value, bytes):
                return json.loads(value.decode())
            elif isinstance(value, str):
                return json.loads(value)
            else:
                return value
        except KeyError:
            print('Missing required key "Value"')
            return value
        except json.JSONDecodeError as err:
            return value

    def as_dict(self):
        return _to_x(self, tgt=dict)

    def clear(self):
        [dict.__delitem__(self, key) for key in self.keys()]

    def delete(self, key):
        self.__delitem__(key)

    def deep_items(self):
        return AD._deep_items(self)

    deepItems = deep_items

    def deep_keys(self):
        return AD._deep_keys(self)

    deepKeys = deep_keys

    def delete_keys(self, keys):
        for k in keys:
            self.delete(k)

    def dump(self, path):
        os.system(f"mkdir -p {os.path.dirname(path)}")
        with open(path, "w") as df:
            df.write(self.dumps())

    def dumps(self):
        return self.jstr()

    def get(self, key, default=None):
        try:
            if default:
                return self.setdefault(key, default=default)
            elif AD.__contains__(self, key):
                return self.__getitem__(key)
            else:
                return None
        except Exception:
            return None

    def items(self):
        return [(k, v) for k, v in dict.items(self) if k != "__dict__"]

    def iteritems(self):
        for k, v in self.items():
            yield (k, v)

    def iterkeys(self):
        return self.__iter__()

    def itervalues(self):
        for _, v in self.items():
            yield v

    def jstr(self):
        return self._json_safe()

    _for_json = jstr
    to_json = jstr

    def keys(self):
        return list(dict.keys(self))

    @staticmethod
    def load(path):
        """Reads json in from a file"""
        if os.path.exists(path):
            with open(path, "r") as fh:
                return AD.loads(fh.read())
        else:
            raise IOError(f"Path does not exists {path}")

    @staticmethod
    def loads(jstr):
        """Reads parses str_in as json, and updates from results"""
        if isinstance(jstr, bytes):
            jstr = jstr.decode("utf-8")
        t = AD._jvalue(jstr)
        if isinstance(t, dict):
            return AD(t)
        elif isinstance(t, list):
            return [AD(d) for d in t]
        else:
            return t

    def pop(self, key):
        value = self.__getitem__(key)
        self.__delitem__(key)
        return (key, value)

    def retrieve(self, mkey, method="glob"):
        res = AD()
        if method == "re":
            rec = re.compile(mkey)
            for key in self.deep_keys():
                if rec.match(key):
                    res[key] = self.__getitem__(key)
        else:
            for key in self.deep_keys():
                if fnmatch(key, mkey):
                    res[key] = self.__getitem__(key)
        return res

    def setdefault(self, key, default):
        try:
            return self.__getitem__(key)
        except KeyError:
            self.__setitem__(key, default)
            return default

    def set_file_persistence(self, path, flush=False):
        """Sets path for persistent json store"""
        myself = self.__myself__(self)
        if path in [".", "..", "./", "/"]:
            raise IOError(f"attribute_dict.set_file_persistence exception invalid path: {path}")
        myself["persistence"] = {}
        myself["persistence"]["mode"] = "file"
        if path[0] not in [".", "/"]:
            path = f"{os.path.dirname(__file__)}/{path}"
        myself["persistence"]["path"] = path
        myself["persistence"]["fname"] = os.path.basename(path)
        myself["persistence"]["dir"] = os.path.dirname(path)
        if not os.path.exists(myself["persistence"]["dir"]):
            os.system(f"mkdir -p {myself['persistence']['dir']}")
        if flush:
            with open(myself["persistence"]["path"], "w") as fh:
                fh.writelines(["{}"])
        if os.path.exists(myself["persistence"]["path"]):
            self.update(self.load(myself["persistence"]["path"]))

    setpersist = set_file_persistence

    def sync(self, **kwargs):
        """Writes text rendering of self to a file"""
        myself = self.__myself__(self)
        if (
            myself
            and "persistence" in myself
            and "mode" in myself["persistence"]
            and myself["persistence"]["mode"] == "file"
        ):
            os.system(f"mkdir -p {myself['persistence']['dir']}")
            with open(myself["persistence"]["path"], "w") as pf:
                pf.write(self.jstr())

    def to_dict(self):
        return _to_x(self, tgt=dict)

    def update(self, *args, **kwargs):
        items = []
        if args and len(args):
            for item in args:
                if item is None:
                    continue
                if isinstance(item, bytes):
                    try:
                        if item[0] == b"[":
                            items.extend(list(json.loads(item.decode("utf-8")).items()))
                        elif item[0] == b'"' and len(item) > 4:
                            items.extend(list(json.loads(item[1:-1].decode()).items()))
                        elif len(item) > 1:
                            items.extend(list(json.loads(item.decode()).items()))
                    except json.JSONDecodeError:
                        pass
                elif isinstance(item, str):
                    try:
                        if item.startswith('''b'"'''):
                            items.extend(list(json.loads(item[3:-3]).items()))
                        elif os.path.exists(item):
                            with open(item) as fh:
                                items.extend(list(json.load(fh).items()))
                    except json.JSONDecodeError:
                        pass
                elif hasattr(item, "deep_items"):
                    items.extend(list(item.deep_items()))
                elif hasattr(item, "items"):
                    items.extend(list(item.items()))
                elif isinstance(item, list) and all(
                    [isinstance(i, tuple) and len(i) == 2 for i in item]
                ):
                    items.extend([e for e in item if len(e) == 2])
                elif isinstance(item, tuple) and len(item) == 2:
                    items.append(item)

        if len(kwargs):
            items += list(kwargs.items())

        for key, value in [
            i for i in items if not isinstance(i, bool) and len(i) == 2 and i[0] is not None
        ]:
            if hasattr(value, "items") and len(value):
                for k, v in value.items():
                    self.__setitem__(f"{key}.{k}", v)
            elif isinstance(value, list) and value.__class__ == "list":
                self.__setitem__(key, [_to_x(v, tgt=AD) for v in value])
            else:
                self.__setitem__(key, value)

    def values(self):
        return list(self.itervalues())


# Mapping.register(AD)


class CAD(AD):
    """
    Dictionary subclass enabling attribute lookup/assignment of keys/values.

    kwargs is leveraged to configure  persistence behavior.
        AWS S3 based persistence
            To use aws s3 persistence, you must call the classmethod AD.set_s3_mgr to set the client up in the classes scope.
            This removes the burden of passing the s3 client object all over the code base.  This is typically set as close to
            module import time as possible.
            - kwargs:
                bucket: str = None -> "tqv-<env>-<cgr>-<bucket-type>"
                can_s3_persist: bool = False -> autopopulated
                key_path: str = None -> "/<namespace>/some/additional/structure"
                open: bool = True -> used when initially creating a versioned resource (means pre-persisted state)
                s3_uri: str = None -> "s3://tqv-<env>-<cgr>-<bucket-type>/<namespace>/some/additional/structure"
                s3_metadata: dict = {} -> hash of metadata to be stored as customer attributes with object
                                          limited to 2KB in size.  A helper function will compress/decompress values if the
                                          hash size exceeds the limit.
                tnumber: int = <integer timestamp or tnumber object -> tnumbers are the major version identifier value used in placing
                                                                       objects on a timeline.  <int major version>_<float minor version>
                tstamp: float = timestamp -> used with tnumber as minor version identifier

        Filesystem based persistence kwargs:
            older local filesystem persistence functionality writing json data to disk.
            - kwargs:
                dir: str = None -> "/filesystem/path" - auto populated from persistTGT
                flush: bool = False -> set to True to zero an existing persisted json object
                fname: str = None ->  "filename.ext" - auto populated from persistTGT
                persistTGT:  str = None -> "/local/filesystem/path"  if the file exists, load it, otherwise initialize it
    """

    consul_value_sig = sorted(
        ["CreateIndex", "ModifyIndex", "LockIndex", "Flags", "Key", "Value", "Session"]
    )
    meta = AD(
        {
            "default": {
                "persistence": {
                    "file": {"dir": None, "flush": None, "fname": None, "path": None},
                    "locked": False,
                    "mode": False,
                    "s3": {
                        "bucket": None,
                        "key_path": None,
                        "metadata": {"tnumber": None, "tstamp": None},
                        "version": None,
                        "uri": None,
                    },
                },
                "subscriptions": {},
            }
        }
    )
    s3_mgr = None

    def __init__(self, *args, **kwargs):
        AD.__init__(self)
        myself = self.__myself__(self)

        if len(kwargs):
            if "persistTGT" in kwargs:
                self.set_file_persistence(kwargs["persistTGT"], flush=kwargs.get("flush"))
                del kwargs["persistTGT"]
                if "flush" in kwargs:
                    del kwargs["flush"]
            if "s3_params" in kwargs:
                self.set_s3_persistence(**kwargs["s3_params"])
                del kwargs["s3_params"]
            if "callbacks" in kwargs:
                for cb, key_path in kwargs["callbacks"]:
                    self.register_callback(cb, key_path)
                del kwargs["callbacks"]
            if "callback" in kwargs:
                if isinstance(kwargs["callback"], tuple):
                    self.register_callback(kwargs["callback"][0], kwargs["callback"][1])
                else:
                    self.register_callback(kwargs["callback"], any)
                del kwargs["callback"]

        self.update(*args)

    def __delitem__(self, key):
        try:
            if isinstance(key, bytes):
                key = key.decode()
            else:
                key = str(key)
            key = key.replace("/", ".")
            key = key.replace("..", ".")
            if key[0] == ".":
                key = key[1:]
            if key[-1] == ".":
                key = key[:-1]
            if "." in key:
                path, key = key.split(".", 1)
                del dict.__getitem__(self, path)[key]
            else:
                dict.__delitem__(self, key)
        except KeyError:
            pass

    def __getattr__(self, key):
        try:
            return self.__getitem__(key)
        except:
            raise AttributeError(key)

    def __getitem__(self, key):
        try:
            if isinstance(key, bytes):
                key = key.decode()
            else:
                key = str(key)
            key = key.replace("/", ".")
            key = key.replace("..", ".")
            if key[0] == ".":
                key = key[1:]
            if key[-1] == ".":
                key = key[:-1]
            if "." in key:
                path, key = key.split(".", 1)
                return dict.__getitem__(self, path)[key]
            else:
                return dict.__getitem__(self, key)
        except:
            raise KeyError(key)

    def __setattr__(self, key, value):
        self.__setitem__(key, value)

    def __setitem__(self, key, value):
        myself = self.__myself__(self)
        if isinstance(key, bytes):
            key = key.decode()
        else:
            key = str(key)
        key = key.replace("/", ".")
        key = key.replace("..", ".")
        if key[0] == ".":
            key = key[1:]
        if key[-1] == ".":
            key = key[:-1]
        value = _to_x(value, tgt=CAD)
        if "." in key:
            path, key = key.split(".", 1)
            if isinstance(dict.setdefault(self, path, CAD()), (AD, CAD, dict)):
                if isinstance(dict.__getitem__(self, path), dict):
                    dict.__setitem__(self, path, _to_x(dict.__getitem__(self, path), tgt=CAD))
            else:
                dict.__setitem__(self, path, CAD())
            dict.__getitem__(self, path).__setitem__(key, value)

        else:
            dict.__setitem__(self, key, value)

        if key in myself["subscriptions"] and len(myself["subscriptions"][key]):
            self.__notify__(key, value)

    def __myself__(self, me, params=None):
        my_id = id(me)
        if my_id not in CAD.meta:
            CAD.meta[my_id] = AD(CAD.meta.default)
            if params and isinstance(params(dict, AD, CAD)):
                CAD.meta[my_id].update(params)
        return CAD.meta[my_id]

    def __notify__(self, key, value):
        myself = self.__myself__(self)
        for k in [any, key]:
            if k in myself["subscriptions"]:
                for cb in myself["subscriptions"][k]:
                    if hasattr(cb, "__call__"):
                        cb(*(key, value))

    @staticmethod
    def _ckvSig(rec):
        if hasattr(rec, "keys"):
            if (
                len([k for k in rec.keys() if k in CAD.consul_value_sig]) >= 5
                and "Key" in rec
                and "Value" in rec
            ):
                return True
        return False

    def delete(self, key):
        key = key.replace("/", ".")
        super().delete(key)

    def get(self, key, default=None):
        key = key.replace("/", ".")
        super().get(key, default=default)

    def put(self, key, value):
        key = key.replace("/", ".")
        super().__setitem__(key, value)

    def register_callback(self, cb, key_path):
        myself = self.__myself__(self)
        if key_path not in myself["subscriptions"]:
            myself["subscriptions"][key_path] = [cb]
        elif cb not in myself["subscriptions"][key_path]:
            myself["subscriptions"][key_path].append(cb)

    def remove_callback(self, key_path, cb):
        myself = self.__myself__(self)
        if myself:
            if key_path in myself["subscriptions"]:
                if cb in myself["subscriptions"]:
                    myself["subscriptions"][key_path].remove(cb)

    def replace(self, replacement):
        self.clear()
        self.update(replacement)

    def set_file_persistence(self, path, flush=False):
        """Sets path for persistent json store"""
        myself = self.__myself__(self)
        myself["persistence.mode"] = "file"
        myself["persistence.file.path"] = path
        myself["persistence.file.fname"] = os.path.basename(path)
        myself["persistence.file.dir"] = os.path.dirname(path)
        if not os.path.exists(myself.persistence.file.dir):
            os.system(f"mkdir -p {myself.persistence.file.dir}")
        if flush:
            with open(myself.persistence.file.path, "w") as fh:
                fh.writelines(["{}"])
        if os.path.exists(myself.persistence.file.path):
            self.update(self.load(myself.persistence.file.path))

    setpersist = set_file_persistence

    def set_s3_mgr(self, s3_mgr):
        if CAD.s3_mgr is None:
            CAD.s3_mgr = s3_mgr

    def set_s3_persistence(self, bucket=None, key=None, metadata={}, uri=None):
        myself = self.__myself__(self)
        myself["persistence.mode"] = "s3"
        if bucket and key:
            myself["persistence.s3.bucket"] = bucket
            myself["persistence.s3.key"] = key
            myself["persistence.s3.uri"] = f"s3://{bucket}/{key}"
        else:
            myself["persistence.s3.uri"] = uri
            bucket, key = uri.split("://")[-1].split("/", 1)
            myself["persistence.s3.bucket"] = bucket
            myself["persistence.s3.key"] = f"/{key}"
        myself["persistence.s3.metadata"].update(metadata)
        if not myself["persistence.s3.metadata"].tnumber:
            myself["persistence.s3.metadata"].tnumber = int(time.time())
        if not myself["persistence.s3.metadata"].tstamp:
            myself["persistence.s3.metadata.tstamp"] = time.time()
        self.s3_load()

    def s3_load(self):
        myself = self.__myself__(self)
        if CAD.s3_mgr:
            try:
                myself["persistence.s3.version"] = CAD.s3_mgr.exists(
                    myself["bucket"], myself["key_path"]
                )
                if myself.persistence.s3.version:
                    myself["s3_metadata"] = CAD.s3_mgr.get_metadata(
                        myself.persistence.s3.bucket, myself.persistence.s3.key
                    )
                    self.update(
                        CAD.s3_mgr.get(myself.persistence.s3.bucket, myself.persistence.s3.key)
                    )
            except Exception as err:
                return Attribute_Dict_Exception(
                    f"CAD.s3_load exception {myself.persistence.s3.uri}: {err}"
                )
        else:
            return Attribute_Dict_Exception(f"CAD.s3_load error: s3_mgr has not been set")

    def sync(self):
        """Writes text rendering of self to a file"""
        myself = self.__myself__(self)
        if myself:
            if myself.persistence.mode == "file":
                self.sync_file()
            elif myself.persistence.mode == "s3":
                self.sync_s3()

    def sync_file(self):
        myself = self.__myself__(self)
        if myself.persistence.mode == "file":
            os.system(f"mkdir -p {myself.persistence.file.dir}")
            with open(myself.persistence.file.path, "w") as pme:
                pme.write(self.jstr())

    def sync_s3(self, force=False):
        myself = self.__myself__(self)
        try:
            if myself.persistence.mode == "s3" and not myself.persistence.s3.version or force:
                myself["persistence.s3.version"] = CAD.s3_mgr.put(
                    myself.persistence.s3.bucket,
                    myself.persistence.s3.key,
                    self.jstr(),
                    metadata=myself.persistence.s3.metadata,
                )
        except Exception as err:
            raise Attribute_Dict_Exception(f"AD.persist exception {myself['s3_uri']}: {err}")

    def update(self, *args, **kwargs):
        items = []
        if args and len(args):
            for item in args:
                if CAD._ckvSig(item):
                    items.extend([(item["Key"].replace("/", "."), CAD._jvalue(item["Value"]))])
                elif isinstance(item, bytes):
                    try:
                        if item[0] == b"[":
                            items.extend(list(json.loads(item.decode("utf-8")).items()))
                        elif item[0] == b'"' and len(item) > 4:
                            items.extend(list(json.loads(item[1:-1].decode()).items()))
                        elif len(item) > 1:
                            items.extend(list(json.loads(item.decode()).items()))
                    except json.JSONDecodeError:
                        pass
                elif isinstance(item, str):
                    try:
                        if item.startswith('''b'"'''):
                            items.extend(list(json.loads(item[3:-3]).items()))
                        elif os.path.exists(item):
                            with open(item) as fh:
                                items.extend(list(json.load(fh).items()))
                    except json.JSONDecodeError:
                        pass
                elif hasattr(item, "items"):
                    items.extend(list(item.items()))
                elif hasattr(item, "keys"):
                    items.extend([(sk, item[sk]) for sk in item.keys()])
                else:
                    items.extend([e for e in item if len(e) == 2])

        if len(kwargs):
            items += list(kwargs.items())

        for key, value in [i for i in filter(None, items) if len(i) == 2]:
            if hasattr(value, "items") and len(value):
                for sk, sv in value.items():
                    super().__setitem__(f"{key}.{sk}", sv)
            elif hasattr(value, "keys") and len(value):
                for sk in value.keys():
                    super().__setitem__(f"{key}.{sk}", value[sk])
            else:
                super().__setitem__(key, value)


ConsulAD = CAD

to_AD = functools.partial(_to_x, tgt=AD)
to_CAD = functools.partial(_to_x, tgt=CAD)
to_DICT = functools.partial(_to_x, tgt=dict)
