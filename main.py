from abc import ABC, abstractmethod

from withdico import DiCoc, resolve


# --- サンプル定義 ---

class Greeter(ABC):
    @abstractmethod
    def greet(self, name: str) -> str: ...


class DefaultGreeter(Greeter):
    def greet(self, name: str) -> str:
        return f"Hello, {name}!"


class App:
    def __init__(self, greeter: Greeter) -> None:
        self.greeter = greeter

    def run(self) -> None:
        print(self.greeter.greet("World"))


# --- 動作確認 ---

def main() -> None:
    # CoC: Greeter (abstract) → DefaultGreeter を自動解決
    app = resolve(App)
    app.run()

    # 同一インスタンスであることを確認（シングルトン）
    app2 = resolve(App)
    print(f"singleton: {app is app2}")

    # register で差し替え
    class MockGreeter(Greeter):
        def greet(self, name: str) -> str:
            return f"Hi, {name}! (mock)"

    DiCoc.register(Greeter, MockGreeter())
    DiCoc.unregister(App)  # App のキャッシュをクリアして再生成させる

    app3 = resolve(App)
    app3.run()


if __name__ == "__main__":
    main()
