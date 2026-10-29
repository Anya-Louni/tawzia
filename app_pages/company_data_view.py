"""Company data: import your file and the app learns from it."""

import pandas as pd
import streamlit as st

from core import appdata, company_data as cd

appdata.sidebar_controls()

st.title("Company data")
st.caption("Import your staff file and attendance log: CV matching, anomaly "
           "detection, KPIs, the simulator and the assistant then learn from YOUR "
           "data. Without an import, everything runs on a clearly labelled demo.")

if cd.is_uploaded():
    st.success(f":material/database: Active source: **{cd.source_label()}**, "
               f"{len(cd.people())} employees, {len(cd.attendance_records())} clock records.",
               icon=":material/check_circle:")
    if st.button("Back to demo data", icon=":material/restart_alt:"):
        cd.clear_company_data()
        st.rerun()
else:
    st.info(":material/science: Active source: **demo data (simulated)**. The "
            "calendar, weather and labour law are real; the workforce is a demo "
            "sample.", icon=":material/info:")

st.divider()

with st.expander("File templates (recognised columns, EN/FR)", icon=":material/table:"):
    st.caption("Column names are matched loosely, in English or French. This is "
               "the expected shape:")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Staff**")
        st.dataframe(cd.workforce_template(), hide_index=True, width="stretch")
        st.download_button("Download the staff template",
                           cd.workforce_template().to_csv(index=False).encode("utf-8"),
                           "staff_template.csv", "text/csv", icon=":material/download:")
    with c2:
        st.markdown("**Attendance / clock-ins**")
        st.dataframe(cd.attendance_template(), hide_index=True, width="stretch")
        st.download_button("Download the attendance template",
                           cd.attendance_template().to_csv(index=False).encode("utf-8"),
                           "attendance_template.csv", "text/csv", icon=":material/download:")

st.subheader("Import")
up1, up2 = st.columns(2)
with up1:
    people_file = st.file_uploader("Staff file (.csv)", type=["csv"], key="up_people")
with up2:
    att_file = st.file_uploader("Attendance log (.csv, optional)", type=["csv"], key="up_att")


def _read_csv(f):
    for sep in (",", ";", "\t"):
        try:
            f.seek(0)
            df = pd.read_csv(f, sep=sep)
            if df.shape[1] > 1:
                return df
        except Exception:
            continue
    f.seek(0)
    return pd.read_csv(f)


if people_file is not None:
    try:
        people = cd.parse_workforce(_read_csv(people_file))
        records = []
        if att_file is not None:
            records = cd.parse_attendance(_read_csv(att_file), people)
        st.markdown(f"**Preview:** {len(people)} employees found"
                    + (f", {len(records)} clock records" if records else ""))
        st.dataframe(pd.DataFrame([{
            "ID": p.emp_id, "Name": p.name, "Role (matched)": p.role_key,
            "Wilaya": p.wilaya, "Contract": p.contract, "Dependants": p.dependants,
        } for p in people[:12]]), hide_index=True, width="stretch")
        if st.button("Use this data", type="primary", icon=":material/upload:"):
            cd.set_company_data(people, records, f"Imported data ({people_file.name})")
            st.success("Data loaded. Every AI page now learns from your file.")
            st.rerun()
    except Exception as exc:
        st.error(f"Could not read the file: {exc}. Check the separator and column "
                 f"headers (see the templates above).")

st.caption(":material/lock: Your files stay in your session; they are neither sent "
           "to an external service nor stored on the server.")
