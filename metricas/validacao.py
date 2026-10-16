"""Avaliação pura da identificação de releases corretivas frente ao consenso."""

from __future__ import annotations

from sklearn.metrics import precision_recall_fscore_support


F1_MINIMO = 0.70


def avaliar_classificacao(reais: list[bool], previstos: list[bool]) -> dict:
    """Precisão, recall e F1 (frações 0–1), contagens e situação da classe corretiva.

    True representa uma release corretiva. Denominadores nulos produzem 0.0,
    conforme zero_division=0; sem corretivas reais a situação é sem_positivos,
    pois não é possível validar a detecção dessa classe. Entradas vazias,
    tamanhos diferentes e valores não booleanos são recusados.
    """
    if not reais or len(reais) != len(previstos):
        raise ValueError("rótulos reais e previstos devem ter o mesmo tamanho não nulo")
    if any(type(valor) is not bool for valor in [*reais, *previstos]):
        raise ValueError("rótulos devem ser booleanos (True = corretiva)")
    precisao, recall, f1, _ = precision_recall_fscore_support(
        reais, previstos, average="binary", pos_label=True, zero_division=0,
    )
    vp = sum(real and previsto for real, previsto in zip(reais, previstos))
    fp = sum(not real and previsto for real, previsto in zip(reais, previstos))
    fn = sum(real and not previsto for real, previsto in zip(reais, previstos))
    vn = sum(not real and not previsto for real, previsto in zip(reais, previstos))
    situacao = ("sem_positivos" if not any(reais) else
                "atingiu_meta" if f1 >= F1_MINIMO else "refinar")
    return {
        "n_itens": len(reais), "n_corretivas_reais": sum(reais),
        "n_corretivas_previstas": sum(previstos),
        "vp": vp, "fp": fp, "fn": fn, "vn": vn,
        "precisao": float(precisao), "recall": float(recall), "f1": float(f1),
        "situacao": situacao,
    }
