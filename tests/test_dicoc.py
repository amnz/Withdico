"""
withdico の単体テスト

テスト対象の機能：
  1. 具象クラスの直接 resolve
  2. CoC（Convention over Configuration）：抽象クラス → DefaultXxx
  3. コンストラクタの自動解決（オートワイヤリング）
  4. シングルトン
  5. register / unregister / is_registered / reset
  6. try_resolve
  7. @package デコレーター（優先順位・複数指定・フォールバック）
  8. Environment 環境変数（環境別サブパッケージの優先検索）
  9. TEST_TOKEN によるテスト分離
 10. エラーケース（実装クラス未発見・型アノテーションなし・循環依存）
"""

import sys
import types
from abc import ABC, abstractmethod

import pytest

from withdico import DiCoc, DiCocCircularDependencyException, DiCocImplementationException, package, resolve


# ── モジュールレベルのテスト用クラス（CoC に必要） ───────────────────────────


class SimpleService:
    """依存なしの具象クラス"""
    def run(self) -> str:
        return "running"


class Greeter(ABC):
    @abstractmethod
    def greet(self, name: str) -> str: ...


class DefaultGreeter(Greeter):
    def greet(self, name: str) -> str:
        return f"Hello, {name}!"


class App:
    """Greeter に依存する具象クラス（オートワイヤリングのテスト用）"""
    def __init__(self, greeter: Greeter) -> None:
        self.greeter = greeter


class NoDefaultAbstract(ABC):
    """実装クラス（DefaultNoDefaultAbstract）が存在しない → 例外"""
    @abstractmethod
    def run(self) -> str: ...


class NoAnnotationService:
    """型アノテーションなしのコンストラクタ引数 → 例外"""
    def __init__(self, dep) -> None:  # noqa: ANN001
        self.dep = dep


# 循環依存: CyclicA → CyclicB → CyclicA
class CyclicA:
    def __init__(self, b: "CyclicB") -> None:
        self.b = b

class CyclicB:
    def __init__(self, a: CyclicA) -> None:
        self.a = a

# 3クラスの循環: CyclicX → CyclicY → CyclicZ → CyclicX
class CyclicX:
    def __init__(self, y: "CyclicY") -> None:
        self.y = y

class CyclicY:
    def __init__(self, z: "CyclicZ") -> None:
        self.z = z

class CyclicZ:
    def __init__(self, x: CyclicX) -> None:
        self.x = x


# ── フィクスチャ ──────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def reset_container():
    """各テスト前後でコンテナをリセットし、テスト間の干渉を防ぐ"""
    DiCoc.reset()
    yield
    DiCoc.reset()


@pytest.fixture()
def extra_modules():
    """テスト中に追加した sys.modules エントリを後片付けするフィクスチャ"""
    added: list[str] = []
    yield added
    for path in added:
        sys.modules.pop(path, None)


def _make_module(path: str, impl_name: str, label: str) -> None:
    """指定パスにフェイクモジュールを登録する。greet() が label を返す実装クラスを持つ。"""
    m = types.ModuleType(path)
    m.__dict__[impl_name] = type(impl_name, (), {"greet": lambda self, n: label})
    sys.modules[path] = m


# ── 1. 基本的な resolve ───────────────────────────────────────────────────────


class TestBasicResolve:
    def test_concrete_class_is_returned_directly(self):
        svc = resolve(SimpleService)
        assert isinstance(svc, SimpleService)

    def test_coc_resolves_abstract_to_default_impl(self):
        """Greeter（ABC）→ DefaultGreeter（同一モジュール）が自動解決される"""
        g = resolve(Greeter)
        assert isinstance(g, DefaultGreeter)

    def test_autowiring_injects_dependencies(self):
        """App(greeter: Greeter) の greeter が自動注入される"""
        app = resolve(App)
        assert isinstance(app, App)
        assert isinstance(app.greeter, DefaultGreeter)

    def test_singleton_same_instance_on_multiple_resolves(self):
        a = resolve(Greeter)
        b = resolve(Greeter)
        assert a is b


# ── 2. register / unregister / is_registered / reset ────────────────────────


class TestRegister:
    def test_registered_instance_overrides_coc(self):
        class MockGreeter(Greeter):
            def greet(self, name: str) -> str:
                return "mocked"

        DiCoc.register(Greeter, MockGreeter())
        assert resolve(Greeter).greet("x") == "mocked"

    def test_unregister_falls_back_to_coc(self):
        class MockGreeter(Greeter):
            def greet(self, name: str) -> str:
                return "mocked"

        DiCoc.register(Greeter, MockGreeter())
        DiCoc.unregister(Greeter)
        assert isinstance(resolve(Greeter), DefaultGreeter)

    def test_is_registered_true_after_register(self):
        DiCoc.register(Greeter, DefaultGreeter())
        assert DiCoc.is_registered(Greeter) is True

    def test_is_registered_false_before_register(self):
        assert DiCoc.is_registered(Greeter) is False

    def test_reset_clears_all_registered_instances(self):
        DiCoc.register(Greeter, DefaultGreeter())
        DiCoc.reset()
        assert DiCoc.is_registered(Greeter) is False

    def test_name_parameter_manages_separate_instances(self):
        class JaGreeter(Greeter):
            def greet(self, name: str) -> str:
                return f"こんにちは、{name}！"

        DiCoc.register(Greeter, DefaultGreeter(), name="en")
        DiCoc.register(Greeter, JaGreeter(), name="ja")
        en = DiCoc.resolve(Greeter, name="en")
        ja = DiCoc.resolve(Greeter, name="ja")

        assert en is not ja
        assert en.greet("W") == "Hello, W!"
        assert ja.greet("W") == "こんにちは、W！"


# ── 3. try_resolve ────────────────────────────────────────────────────────────


class TestTryResolve:
    def test_returns_none_when_not_registered(self):
        assert DiCoc.try_resolve(Greeter) is None

    def test_fallback_is_called_and_result_is_registered(self):
        class MockGreeter(Greeter):
            def greet(self, name: str) -> str:
                return "fallback"

        mock = MockGreeter()
        result = DiCoc.try_resolve(Greeter, if_not_registered=lambda: mock)
        assert result is mock
        assert DiCoc.is_registered(Greeter)

    def test_returns_existing_instance_when_registered(self):
        g = DefaultGreeter()
        DiCoc.register(Greeter, g)
        assert DiCoc.try_resolve(Greeter) is g


# ── 4. @package デコレーター ──────────────────────────────────────────────────


class TestPackageDecorator:
    def test_package_takes_priority_over_same_module(self, extra_modules):
        _make_module("pkg.api", "DefaultPkgGreeter", "from pkg.api")
        extra_modules.append("pkg.api")

        @package("pkg.api")
        class PkgGreeter(ABC):
            @abstractmethod
            def greet(self, name: str) -> str: ...

        # 同一モジュールにも DefaultPkgGreeter は存在しないが、pkg.api で見つかる
        g = resolve(PkgGreeter)
        assert g.greet("x") == "from pkg.api"

    def test_multiple_packages_searched_in_written_order(self, extra_modules):
        """記述順（上が優先）で検索される"""
        _make_module("pkg.first", "DefaultOrderGreeter", "first")
        _make_module("pkg.second", "DefaultOrderGreeter", "second")
        extra_modules += ["pkg.first", "pkg.second"]

        @package("pkg.first")
        @package("pkg.second")
        class OrderGreeter(ABC):
            @abstractmethod
            def greet(self, name: str) -> str: ...

        g = resolve(OrderGreeter)
        assert g.greet("x") == "first"

    def test_falls_back_to_next_package_when_first_missing(self, extra_modules):
        _make_module("pkg.b", "DefaultFallbackGreeter", "from b")
        extra_modules.append("pkg.b")

        @package("pkg.missing")   # 存在しない → スキップ
        @package("pkg.b")
        class FallbackGreeter(ABC):
            @abstractmethod
            def greet(self, name: str) -> str: ...

        g = resolve(FallbackGreeter)
        assert g.greet("x") == "from b"


# ── 5. Environment 環境変数 ───────────────────────────────────────────────────


class TestEnvironment:
    def test_env_subpackage_takes_priority_over_base_package(
        self, monkeypatch, extra_modules
    ):
        _make_module("conf", "DefaultEnvGreeter", "conf")
        _make_module("conf.staging", "DefaultEnvGreeter", "conf.staging")
        extra_modules += ["conf", "conf.staging"]
        monkeypatch.setenv("Environment", "staging")

        @package("conf")
        class EnvGreeter(ABC):
            @abstractmethod
            def greet(self, name: str) -> str: ...

        g = resolve(EnvGreeter)
        assert g.greet("x") == "conf.staging"

    def test_without_env_uses_base_package(self, monkeypatch, extra_modules):
        _make_module("conf2", "DefaultBase2Greeter", "conf2")
        extra_modules.append("conf2")
        monkeypatch.delenv("Environment", raising=False)

        @package("conf2")
        class Base2Greeter(ABC):
            @abstractmethod
            def greet(self, name: str) -> str: ...

        g = resolve(Base2Greeter)
        assert g.greet("x") == "conf2"

    def test_full_search_order_with_multiple_packages_and_env(
        self, monkeypatch, extra_modules
    ):
        """
        @package('tool.config') @package('config')、Environment=staging の検索順：
        1. tool.config.staging  ← 最優先
        2. config.staging
        3. (同一モジュール).staging
        4. tool.config
        5. config
        6. (同一モジュール)
        """
        for p in ["tool.config", "tool.config.staging", "conf3", "conf3.staging"]:
            _make_module(p, "DefaultFullOrderGreeter", p)
        extra_modules += ["tool.config", "tool.config.staging", "conf3", "conf3.staging"]
        monkeypatch.setenv("Environment", "staging")

        @package("tool.config")
        @package("conf3")
        class FullOrderGreeter(ABC):
            @abstractmethod
            def greet(self, name: str) -> str: ...

        g = resolve(FullOrderGreeter)
        assert g.greet("x") == "tool.config.staging"

    def test_env_falls_through_to_same_module_when_subpackage_missing(
        self, monkeypatch
    ):
        """Environment 指定があっても同一モジュールの実装にフォールバックする"""
        monkeypatch.setenv("Environment", "staging")
        # tests.test_dicoc.staging は存在しないため、tests.test_dicoc の DefaultGreeter へ
        g = resolve(Greeter)
        assert isinstance(g, DefaultGreeter)


# ── 6. TEST_TOKEN によるテスト分離 ────────────────────────────────────────────


class TestTestToken:
    def test_different_tokens_yield_different_singletons(self, monkeypatch):
        monkeypatch.setenv("TEST_TOKEN", "token_a")
        a = resolve(SimpleService)

        monkeypatch.setenv("TEST_TOKEN", "token_b")
        b = resolve(SimpleService)

        assert a is not b

    def test_same_token_yields_same_singleton(self, monkeypatch):
        monkeypatch.setenv("TEST_TOKEN", "shared")
        a = resolve(SimpleService)
        b = resolve(SimpleService)
        assert a is b


# ── 7. エラーケース ───────────────────────────────────────────────────────────


class TestErrors:
    def test_no_default_impl_raises_exception(self):
        """DefaultNoDefaultAbstract が存在しない場合は DiCocImplementationException"""
        with pytest.raises(DiCocImplementationException):
            resolve(NoDefaultAbstract)

    def test_constructor_param_without_annotation_raises_type_error(self):
        """型アノテーションのないコンストラクタ引数は TypeError"""
        with pytest.raises(TypeError, match="has no type annotation"):
            resolve(NoAnnotationService)

    def test_circular_dependency_raises_exception(self):
        """A → B → A の循環依存は DiCocCircularDependencyException"""
        with pytest.raises(DiCocCircularDependencyException):
            resolve(CyclicA)

    def test_circular_dependency_message_shows_cycle(self):
        """エラーメッセージに循環のパスが含まれる"""
        with pytest.raises(DiCocCircularDependencyException, match=r"CyclicA.*CyclicB.*CyclicA"):
            resolve(CyclicA)

    def test_three_class_circular_dependency(self):
        """X → Y → Z → X の3クラスの循環依存も検出される"""
        with pytest.raises(DiCocCircularDependencyException, match=r"CyclicX.*CyclicY.*CyclicZ.*CyclicX"):
            resolve(CyclicX)
