"""
workforce_chat
--------------
L'interface de conversation de WorkForce.dz, bâtie sur assistant-ui.

Le fil de discussion est piloté par un *external store* : **Python détient la
vérité** (la liste des messages), le composant React l'affiche, et chaque envoi
remonte par un déclencheur CCv2. C'est le bon découpage ici pour une raison de
sécurité autant que d'architecture , la réponse est produite côté serveur par
Groq et par les moteurs maison, donc **aucune clé d'API ne descend jamais dans
le navigateur**.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

import streamlit as st

_COMPONENT = st.components.v2.component(
    "workforce-chat.workforce_chat",
    js="index-*.js",
    html='<div class="react-root"></div>',
)


def workforce_chat(
    messages: list,
    *,
    busy: bool = False,
    placeholder: str = "Posez votre question…",
    suggestions: Optional[list] = None,
    empty_title: str = "Que voulez-vous savoir ?",
    empty_text: str = "",
    key: str = "workforce_chat",
    on_sent: Optional[Callable[[], None]] = None,
) -> Any:
    """
    Afficher le fil de conversation et renvoyer le message envoyé, s'il y en a un.

    Parameters
    ----------
    messages:
        La conversation, du plus ancien au plus récent : une liste de
        dictionnaires ``{"role": "user" | "assistant" | "system",
        "content": str}``.
    busy:
        Vrai pendant que la réponse se calcule , affiche l'indicateur de saisie
        et désactive le bouton d'envoi.
    suggestions:
        Questions proposées tant que le fil est vide.
    on_sent:
        Rappel déclenché quand l'utilisateur envoie un message.

    Returns
    -------
    Le résultat du composant. ``result.sent`` porte le texte envoyé lors de ce
    rerun, ou ``None``.
    """
    return _COMPONENT(
        key=key,
        data={
            "messages": messages,
            "busy": bool(busy),
            "placeholder": placeholder,
            "suggestions": suggestions or [],
            "emptyTitle": empty_title,
            "emptyText": empty_text,
        },
        on_sent_change=on_sent if on_sent is not None else (lambda: None),
    )
