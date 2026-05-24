import inspect
import os
import sys
import typing
from typing import Callable, TypeVar

T = TypeVar("T")

DEFAULT_NAME = "primary"
_IMPL_PREFIX = "Default"


class DiCocImplementationException(Exception):
    def __init__(self, impl_name: str) -> None:
        super().__init__(
            f"Implementation class '{impl_name}' not found. "
            f"Convention: Xxx (abstract) → Default + Xxx must exist in the same module."
        )


class DiCoc:
    DEFAULT_NAME = "primary"

    _me: "DiCoc | None" = None

    def __init__(self) -> None:
        self._singletons: dict[str, object] = {}
        DiCoc._me = self

    @classmethod
    def _get_instance(cls) -> "DiCoc":
        if cls._me is None:
            cls._me = cls()
        return cls._me

    @classmethod
    def reset(cls) -> None:
        """登録・初期化済みシングルトンをすべてリセット"""
        cls._get_instance()._singletons = {}

    def _type_key(self, type_: type, name: str) -> str:
        test_token = os.environ.get("TEST_TOKEN", "")
        full_name = f"{type_.__module__}.{type_.__qualname__}"
        return f"{full_name}@{name}{test_token}"

    @classmethod
    def register(cls, type_: type[T], instance: T, name: str = DEFAULT_NAME) -> None:
        """シングルトン事前登録"""
        di = cls._get_instance()
        di._singletons[di._type_key(type_, name)] = instance  # type: ignore[assignment]

    @classmethod
    def unregister(cls, type_: type[T], name: str = DEFAULT_NAME) -> None:
        """シングルトン登録解除"""
        di = cls._get_instance()
        di._singletons.pop(di._type_key(type_, name), None)

    @classmethod
    def is_registered(cls, type_: type[T], name: str = DEFAULT_NAME) -> bool:
        """指定された type がすでに登録されているか確認"""
        di = cls._get_instance()
        return di._type_key(type_, name) in di._singletons

    @classmethod
    def resolve(cls, type_: type[T], name: str = DEFAULT_NAME) -> T:
        """指定された type の実装クラスのシングルトンを取得（なければ自動生成）"""
        return cls._get_instance()._find(type_, name)

    @classmethod
    def try_resolve(
        cls,
        type_: type[T],
        name: str = DEFAULT_NAME,
        if_not_registered: Callable[[], T] | None = None,
    ) -> T | None:
        """登録済みなら返す。未登録なら if_not_registered() を呼び登録して返す。引数なしなら None を返す。"""
        if not cls.is_registered(type_, name):
            if if_not_registered is None:
                return None
            instance = if_not_registered()
            cls.register(type_, instance, name)
            return instance
        return cls.resolve(type_, name)

    def _find(self, type_: type[T], name: str = DEFAULT_NAME) -> T:
        key = self._type_key(type_, name)
        if key in self._singletons:
            return self._singletons[key]  # type: ignore[return-value]

        impl_cls = self._resolve_implementation(type_)

        hints = typing.get_type_hints(impl_cls.__init__)
        sig = inspect.signature(impl_cls.__init__)

        args: list[object] = []
        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue
            if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
                continue
            param_type = hints.get(param_name)
            if param_type is None:
                raise TypeError(
                    f"Constructor parameter '{param_name}' of '{impl_cls.__qualname__}' "
                    f"has no type annotation. DiCoc requires type hints for auto-wiring."
                )
            args.append(self._find(param_type))

        result: T = impl_cls(*args)  # type: ignore[call-arg]
        self._singletons[key] = result  # type: ignore[assignment]
        return result

    def _resolve_implementation(self, type_: type) -> type:
        """
        CoC (Convention over Configuration):
        抽象クラス（ABCやProtocol）の場合、同じモジュール内の "Default" + クラス名 を実装とする。
        具象クラスの場合はそのまま使用する。
        """
        if not inspect.isabstract(type_):
            return type_

        impl_name = _IMPL_PREFIX + type_.__name__
        module = sys.modules.get(type_.__module__)
        impl_cls = getattr(module, impl_name, None) if module else None

        if not isinstance(impl_cls, type):
            raise DiCocImplementationException(impl_name)

        return impl_cls


def resolve(type_: type[T], name: str = DiCoc.DEFAULT_NAME) -> T:
    """DiCoc.resolve() のショートカット関数"""
    return DiCoc.resolve(type_, name)
