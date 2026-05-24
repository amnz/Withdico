# withdico

Python 向けの軽量な依存性注入（DI）コンテナです。
Convention over Configuration（CoC）により、設定ファイル不要でクラスを自動解決します。

## インストール

```bash
pip install withdico
# または
uv add withdico
```

## 基本的な使い方

### 1. 抽象クラスと実装クラスを定義する

命名規則：抽象クラス `Xxx` に対して、実装クラスは `DefaultXxx` とします。
抽象クラスと実装クラスは**同じモジュール**に配置します。

```python
from abc import ABC, abstractmethod
from withdico import resolve

class Greeter(ABC):
    @abstractmethod
    def greet(self, name: str) -> str: ...

class DefaultGreeter(Greeter):
    def greet(self, name: str) -> str:
        return f"Hello, {name}!"

class App:
    def __init__(self, greeter: Greeter) -> None:
        self.greeter = greeter

# Greeter → DefaultGreeter を自動解決し、App のコンストラクタに注入
app = resolve(App)
app.greeter.greet("World")  # "Hello, World!"
```

コンストラクタの引数は型アノテーションを元に再帰的に解決されます（オートワイヤリング）。
型アノテーションが付いていないコンストラクタ引数がある場合は `TypeError` が発生します。

### 2. シングルトン

同じ型を複数回 resolve しても、同一インスタンスが返ります。

```python
app1 = resolve(App)
app2 = resolve(App)
assert app1 is app2  # True
```

### 3. テスト時のモック差し替え

```python
from withdico import DiCoc

class MockGreeter(Greeter):
    def greet(self, name: str) -> str:
        return "mocked!"

DiCoc.register(Greeter, MockGreeter())
DiCoc.unregister(App)  # App のキャッシュをクリアして再生成させる

app = resolve(App)
app.greeter.greet("World")  # "mocked!"
```

テスト間でシングルトンをすべてリセットしたい場合：

```python
DiCoc.reset()
```

### 4. 複数インスタンスの管理（name 引数）

同じ型に対して複数のインスタンスを名前で使い分けることができます。

```python
DiCoc.register(Greeter, JaGreeter(), name="ja")
DiCoc.register(Greeter, EnGreeter(), name="en")

ja = DiCoc.resolve(Greeter, name="ja")
en = DiCoc.resolve(Greeter, name="en")
```

---

## @package デコレーター

抽象クラスに `@package` デコレーターを付けることで、実装クラスの**検索先モジュール**を指定できます。
同一モジュールより優先して検索されます。

```python
from withdico import package

@package('myproject.api')
class Greeter(ABC):
    @abstractmethod
    def greet(self, name: str) -> str: ...
```

`myproject.api` モジュール内の `DefaultGreeter` が優先して使用されます。

### 複数指定

複数の `@package` を重ねて指定でき、**記述順（上が優先）**に検索されます。

```python
@package('myproject.api')   # 1番目に検索
@package('myproject.impl')  # 2番目に検索
class Greeter(ABC):
    ...
# 検索順: myproject.api → myproject.impl → 同一モジュール（フォールバック）
```

---

## Environment 環境変数による環境別切り替え

環境変数 `Environment` を設定すると、各検索先パッケージの**サブパッケージ**が優先して検索されます。
開発・ステージング・本番など環境ごとに実装を切り替えるために使用します。

```bash
Environment=staging python main.py
```

`@package('tool.config') @package('config')` が指定されていて `Environment=staging` の場合、
以下の順で `DefaultXxx` クラスを検索します：

```
1. tool.config.staging   ← 環境別サブパッケージを優先
2. config.staging
3. (同一モジュール).staging
4. tool.config           ← 環境変数なしと同じ検索
5. config
6. (同一モジュール)
```

### 使用例

```python
# myproject/config/staging/greeter.py
class DefaultGreeter(Greeter):
    def greet(self, name: str) -> str:
        return "Staging environment!"
```

```python
# myproject/service.py
@package('myproject.config')
class Greeter(ABC):
    @abstractmethod
    def greet(self, name: str) -> str: ...
```

```bash
# ステージング環境で起動
Environment=staging python main.py
# → myproject.config.staging.DefaultGreeter が使用される
```

---

## テスト分離（TEST_TOKEN）

環境変数 `TEST_TOKEN` を設定すると、シングルトンのキーにトークンが付加されます。
並列テストなど、テスト間でシングルトンを分離したい場合に使用します。

```python
# pytest の場合
def test_a(monkeypatch):
    monkeypatch.setenv("TEST_TOKEN", "test_a")
    svc = resolve(MyService)  # test_a 専用のインスタンス

def test_b(monkeypatch):
    monkeypatch.setenv("TEST_TOKEN", "test_b")
    svc = resolve(MyService)  # test_b 専用のインスタンス（test_a とは別）
```

---

## API リファレンス

| API | 説明 |
|---|---|
| `resolve(Type)` | シングルトン取得（CoC で自動生成） |
| `DiCoc.resolve(Type, name)` | `resolve()` と同じ（name 指定可） |
| `DiCoc.register(Type, instance, name)` | インスタンスを事前登録 |
| `DiCoc.unregister(Type, name)` | 登録解除 |
| `DiCoc.is_registered(Type, name)` | 登録済みか確認 |
| `DiCoc.try_resolve(Type, name, if_not_registered)` | 未登録なら `None` またはフォールバック |
| `DiCoc.reset()` | 全シングルトンをリセット |
| `@package(module_path)` | 実装クラスの検索先モジュールを指定（複数可） |

## Convention over Configuration

```
Greeter (ABC)  →  DefaultGreeter
```

抽象クラスを `resolve()` すると、以下の優先順位で `DefaultXxx` クラスを探します：

1. `@package` で指定されたモジュール（記述順）
2. 同一モジュール（フォールバック）

`Environment` 環境変数が設定されている場合は、各候補の `.{env}` サブパッケージが先に検索されます。

明示的に `register()` した場合はすべての CoC より優先されます。

## ライセンス

MIT License
