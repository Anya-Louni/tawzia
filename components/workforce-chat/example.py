"""
Exemple minimal du composant de conversation, utile pendant son développement.

    streamlit run example.py

Python détient la conversation ; le composant l'affiche et renvoie le message
envoyé. C'est le même découpage que dans l'application, à ceci près que la
réponse est ici une chaîne inversée plutôt qu'un appel au modèle.
"""

import streamlit as st

from workforce_chat import workforce_chat

st.set_page_config(page_title="workforce-chat", layout="wide")
st.title("Composant de conversation , exemple")

st.session_state.setdefault("messages", [])
st.session_state.setdefault("pending", None)

result = workforce_chat(
    st.session_state["messages"],
    busy=st.session_state["pending"] is not None,
    placeholder="Posez une question…",
    suggestions=[
        "Combien de personnes faut-il demain ?",
        "Quel est l'effet du Ramadan sur la charge ?",
    ],
    empty_title="Que voulez-vous savoir ?",
    empty_text="Exemple de développement : la réponse renvoie simplement le "
               "message à l'envers.",
    key="example_thread",
)

sent = getattr(result, "sent", None)

# Deux temps : on affiche d'abord la question et l'indicateur de saisie, puis on
# produit la réponse au rerun suivant.
if sent and st.session_state["pending"] is None:
    st.session_state["messages"].append({"role": "user", "content": sent})
    st.session_state["pending"] = sent
    st.rerun()

if st.session_state["pending"] is not None:
    st.session_state["messages"].append({
        "role": "assistant",
        "content": st.session_state["pending"][::-1],
    })
    st.session_state["pending"] = None
    st.rerun()

st.caption(f"{len(st.session_state['messages'])} messages dans le fil.")
