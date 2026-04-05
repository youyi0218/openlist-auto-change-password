from __future__ import annotations

import secrets
import string


def generate_password(policy) -> str:
    pools: list[str] = []
    if policy.use_lowercase:
        pools.append(string.ascii_lowercase)
    if policy.use_uppercase:
        pools.append(string.ascii_uppercase)
    if policy.use_numbers:
        pools.append(string.digits)
    if policy.use_symbols:
        pools.append(policy.symbols)

    if not pools:
        raise ValueError("未启用任何密码字符集")
    if policy.length < len(pools):
        raise ValueError("密码长度不能小于已启用字符集数量")

    password_chars = [secrets.choice(pool) for pool in pools]
    merged = "".join(pools)
    while len(password_chars) < policy.length:
        password_chars.append(secrets.choice(merged))
    secrets.SystemRandom().shuffle(password_chars)
    return "".join(password_chars)
