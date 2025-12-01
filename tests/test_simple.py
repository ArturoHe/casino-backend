# tests/test_simple.py
def test_simple():
    """Test básico para verificar que pytest funciona"""
    assert 1 + 1 == 2

def test_another():
    """Otro test simple"""
    assert "hello".upper() == "HELLO"

print("hola")