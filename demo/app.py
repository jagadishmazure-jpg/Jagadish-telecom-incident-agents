"""Thin Streamlit demo for the telecom NOC assistant.

All logic lives in telcoops/ (via telcoops.demo_helpers); this file only
wires widgets. streamlit is imported lazily inside main() so importing this
module never breaks the stdlib test suite.

Live run:
    pip install streamlit
    streamlit run demo/app.py
"""

import os

SOPS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "docs", "sops")


def main():
    import sys

    import streamlit as st  # lazy: keeps stdlib tests dependency-free

    # `streamlit run demo/app.py` puts demo/ on sys.path; telcoops/ lives one up.
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from telcoops import demo_helpers, orchestrator

    st.set_page_config(page_title="Telecom NOC Assistant", layout="wide")
    st.title("Telecom NOC Assistant (demo)")

    if "orch" not in st.session_state:
        conn = demo_helpers.build_demo_db()
        st.session_state["orch"] = orchestrator.Orchestrator(conn, SOPS_DIR)

    orch = st.session_state["orch"]
    q = st.selectbox("Ask the NOC assistant", demo_helpers.demo_questions())
    if st.button("Run"):
        r = orch.handle(q)
        st.write(f"**Tier:** {r['tier']}")
        st.write(r["answer"])
        if r["citations"]:
            st.caption("Citations: " + ", ".join(r["citations"]))

    st.subheader("Alarm correlation (seeded storm)")
    if st.button("Correlate alarms"):
        st.json(demo_helpers.demo_correlation())

    st.subheader("Dispatch recommendation")
    if st.button("Recommend fiber tech (SITE-WEST)"):
        st.json(demo_helpers.demo_dispatch())


if __name__ == "__main__":
    main()
