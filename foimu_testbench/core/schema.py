"""Small strict JSON/dataclass boundary, intentionally independent of the simulator."""
import json
import math
import types
from dataclasses import dataclass, fields
from typing import Literal, Union, get_args, get_origin, get_type_hints


def json_value(value):
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float and math.isfinite(value):
        return
    if type(value) is list:
        for item in value:
            json_value(item)
        return
    if type(value) is dict and all(type(k) is str for k in value):
        for item in value.values():
            json_value(item)
        return
    raise ValueError('Valor deve ser JSON finito, sem objetos Python')


def checked(value, hint, path, decode=False):
    origin, args = get_origin(hint), get_args(hint)
    if origin in (Union, types.UnionType):
        for option in args:
            try:
                return checked(value, option, path, decode)
            except (ValueError, TypeError):
                pass
        raise ValueError(f'{path}: tipo/valor inválido para {hint}')
    if origin is Literal:
        if not any(type(value) is type(x) and value == x for x in args):
            raise ValueError(f'{path}: esperado um de {args}')
    elif origin in (list, dict):
        if type(value) is not origin:
            raise ValueError(f'{path}: esperado {origin.__name__}')
        if origin is list:
            return [checked(v,args[0],f'{path}[{i}]',decode) for i,v in enumerate(value)]
        return {checked(k,args[0],path,decode):checked(v,args[1],f'{path}.{k}',decode) for k,v in value.items()}
    elif isinstance(hint, type) and issubclass(hint, Model):
        if decode and type(value) is dict:
            return hint.from_dict(value)
        if type(value) is not hint:
            raise ValueError(f'{path}: esperado {hint.__name__}')
        value.__post_init__()
    elif hint is object:
        json_value(value)
    elif type(value) is not hint:
        raise ValueError(f'{path}: esperado {hint.__name__}, recebido {type(value).__name__}')
    elif hint is float and not math.isfinite(value):
        raise ValueError(f'{path}: número deve ser finito')
    elif hint is str and not value.strip():
        raise ValueError(f'{path}: texto não pode ser vazio')
    return value


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique(values, label):
    require(len(values)==len(set(values)), f'{label}: IDs duplicados')


def _pairs(pairs):
    result={}
    for k,v in pairs:
        require(k not in result, f'JSON: chave duplicada {k}')
        result[k]=v
    return result


@dataclass(frozen=True, kw_only=True)
class Model:
    schema_version: Literal[2] = 2

    def __post_init__(self):
        for name,hint in get_type_hints(type(self)).items():
            checked(getattr(self,name),hint,f'{type(self).__name__}.{name}')
        self.validate()

    def validate(self):
        pass

    @classmethod
    def from_dict(cls, data):
        require(type(data) is dict, f'{cls.__name__}: esperado objeto JSON')
        names={f.name for f in fields(cls)}
        require(not set(data)-names, f'{cls.__name__}: chaves desconhecidas {set(data)-names}')
        require('schema_version' in data, f'{cls.__name__}: schema_version obrigatório no JSON')
        hints=get_type_hints(cls)
        try:
            return cls(**{k:checked(v,hints[k],f'{cls.__name__}.{k}',True) for k,v in data.items()})
        except TypeError as exc:
            raise ValueError(f'{cls.__name__}: campos obrigatórios ausentes: {exc}') from exc

    @classmethod
    def from_json(cls, text):
        return cls.from_dict(json.loads(text, object_pairs_hook=_pairs,
            parse_constant=lambda x: (_ for _ in ()).throw(ValueError(f'JSON não finito: {x}'))))

    def to_dict(self):
        self.__post_init__()
        def plain(v):
            if isinstance(v, Model):
                return v.to_dict()
            if type(v) is list:
                return [plain(x) for x in v]
            if type(v) is dict:
                return {k:plain(x) for k,x in v.items()}
            return v
        return {f.name:plain(getattr(self,f.name)) for f in fields(self)}

    def to_json(self):
        return json.dumps(self.to_dict(),sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':'))
