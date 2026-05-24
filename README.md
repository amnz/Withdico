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

# Greeter → DefaultGreeter を自動解決し、App を生成
app = resolve(App)
app.greeter.greet("World")  # "Hello, World!"
```

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
DiCoc.unregister(App)  # キャッシュをクリアして再生成させる

app = resolve(App)
app.greeter.greet("World")  # "mocked!"
```

テスト間でシングルトンをリセットしたい場合：

```python
DiCoc.reset()
```

### 4. 複数インスタンスの管理（name 引数）

```python
DiCoc.register(Greeter, JaGreeter(), name="ja")
DiCoc.register(Greeter, EnGreeter(), name="en")

ja = DiCoc.resolve(Greeter, name="ja")
en = DiCoc.resolve(Greeter, name="en")
```

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

## Convention over Configuration

抽象クラス（`ABC` のサブクラス）を `resolve()` すると、**同じモジュール内**の `Default` + クラス名のクラスを実装として自動解決します。

```
Greeter (ABC)  →  DefaultGreeter  （同じモジュール内に存在すること）
```

明示的に `register()` した場合は CoC より優先されます。

## ライセンス

MIT License
