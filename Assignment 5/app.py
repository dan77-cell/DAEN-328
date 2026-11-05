"""DAEN 328 Assignment 5, Part C. Run: python -m streamlit run app.py
Set DB_PASSWORD in your terminal environment before running; do not submit credentials.
"""
import math
import os

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

st.set_page_config(page_title="EmployeeDB Dashboard", page_icon="📊", layout="wide")

@st.cache_resource
def get_engine():
    password = os.getenv("DB_PASSWORD", "ADO7104v")
    if not password:
        raise ValueError("Set DB_PASSWORD in your terminal before launching Streamlit.")
    return create_engine(URL.create(
        "postgresql+psycopg2", username=os.getenv("DB_USER", "postgres"),
        password=password, host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")), database=os.getenv("DB_NAME", "EmployeeDB")
    ), pool_pre_ping=True)

@st.cache_data(ttl=600)
def run_query(sql, params=None):
    with get_engine().connect() as conn:
        return pd.read_sql(text(sql), conn, params=params)

st.title("EmployeeDB | Workforce & Salary Dashboard")
st.caption("DAEN 328 Assignment 5 — live data from PostgreSQL")

try:
    divisions = run_query("SELECT divtype FROM divisions ORDER BY divtype")["divtype"].tolist()
    departments = run_query("SELECT departmentname FROM departments ORDER BY departmentname")["departmentname"].tolist()
    bounds = run_query("SELECT MIN(salary) AS min_salary, MAX(salary) AS max_salary FROM employeedetails")
except Exception as exc:
    st.error("Unable to read EmployeeDB. Check PostgreSQL and DB_* environment settings.")
    st.exception(exc)
    st.stop()

if bounds.empty or pd.isna(bounds.loc[0, "min_salary"]):
    st.warning("No employee salaries available. Complete Part A first.")
    st.stop()

st.sidebar.header("Filters")
selected_divisions = st.sidebar.multiselect("Division", divisions, default=divisions)
selected_department = st.sidebar.selectbox("Department", ["All"] + departments)
# Use floor/ceil so default FULL range includes fractional-cent endpoints.
min_salary = math.floor(float(bounds.loc[0, "min_salary"]))
max_salary = math.ceil(float(bounds.loc[0, "max_salary"]))
if min_salary < max_salary:
    salary_low, salary_high = st.sidebar.slider(
        "Salary range ($)", min_value=min_salary, max_value=max_salary,
        value=(min_salary, max_salary), step=1, format="$%d"
    )
else:
    salary_low = salary_high = min_salary
    st.sidebar.write(f"Salary: ${min_salary:,}")

if not selected_divisions:
    st.warning("Select at least one division.")
    st.stop()

# All five queries use the same parameterized filter so EVERY visual follows filters.
FILTER_SQL = """
FROM employeedetails e
JOIN personaldetails p ON e.ssn = p.ssn
JOIN divisions v ON e.divisionid = v.divisionid
JOIN departments d ON e.departmentid = d.departmentid
JOIN jobtitles j ON e.jobtitleid = j.jobtitleid
WHERE v.divtype = ANY(:divisions)
  AND (:department = 'All' OR d.departmentname = :department)
  AND e.salary BETWEEN :salary_low AND :salary_high
"""
params = {"divisions": selected_divisions, "department": selected_department,
          "salary_low": salary_low, "salary_high": salary_high}

try:
    # 1. Three required KPIs (median computed by PostgreSQL).
    kpi = run_query("""
        SELECT COUNT(*) AS headcount,
               AVG(e.salary) AS average_salary,
               PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY e.salary) AS median_salary
    """ + FILTER_SQL, params).iloc[0]
    x, y, z = st.columns(3)
    x.metric("Headcount", f"{int(kpi['headcount']):,}")
    y.metric("Average salary", f"${float(kpi['average_salary']):,.2f}" if pd.notna(kpi['average_salary']) else "—")
    z.metric("Median salary", f"${float(kpi['median_salary']):,.2f}" if pd.notna(kpi['median_salary']) else "—")

    if not int(kpi["headcount"]):
        st.info("No employees match these filters.")
        st.stop()

    # 2. Headcount by department.
    by_department = run_query("""
        SELECT d.departmentname AS department, COUNT(*) AS headcount
    """ + FILTER_SQL + " GROUP BY d.departmentname ORDER BY headcount DESC", params)
    fig = px.bar(by_department.sort_values("headcount"), x="headcount", y="department",
                 orientation="h", title="Headcount by department",
                 labels={"headcount": "Employees", "department": "Department"})
    st.plotly_chart(fig, width="stretch")

    # 3. Box plot: salaries by DIVISION.
    salaries = run_query("""
        SELECT v.divtype AS division, e.salary AS salary
    """ + FILTER_SQL, params)
    fig = px.box(salaries, x="division", y="salary", points="outliers",
                 title="Salary distribution by division",
                 labels={"division": "Division", "salary": "Salary ($)"})
    st.plotly_chart(fig, width="stretch")

    # 4. Age bands computed in PostgreSQL from birthdate, displayed in required order.
    by_age = run_query("""
        WITH ages AS (
            SELECT e.salary,
                CASE
                    WHEN EXTRACT(YEAR FROM AGE(CURRENT_DATE, p.birthdate)) < 30 THEN 'Under 30'
                    WHEN EXTRACT(YEAR FROM AGE(CURRENT_DATE, p.birthdate)) < 40 THEN '30-39'
                    WHEN EXTRACT(YEAR FROM AGE(CURRENT_DATE, p.birthdate)) < 50 THEN '40-49'
                    WHEN EXTRACT(YEAR FROM AGE(CURRENT_DATE, p.birthdate)) < 60 THEN '50-59'
                    ELSE '60+'
                END AS age_band
        """ + FILTER_SQL + """ AND p.birthdate IS NOT NULL
        )
        SELECT age_band, COUNT(*) AS employees, AVG(salary) AS average_salary
        FROM ages GROUP BY age_band
    """, params)
    age_order = ["Under 30", "30-39", "40-49", "50-59", "60+"]
    fig = px.bar(by_age, x="age_band", y="average_salary", text="employees",
                 category_orders={"age_band": age_order},
                 hover_data={"employees": True, "average_salary": ":,.2f"},
                 title="Average salary by age band (bar labels = employee count)",
                 labels={"age_band": "Age band", "average_salary": "Average salary ($)",
                         "employees": "Employees in band"})
    fig.update_traces(textposition="outside")
    fig.update_layout(xaxis={"categoryorder": "array", "categoryarray": age_order})
    st.plotly_chart(fig, width="stretch")

    # 5. TOP TEN based on average salary, NOT headcount.
    by_title = run_query("""
        SELECT j.jobtitle AS job_title, COUNT(*) AS employees,
               AVG(e.salary) AS average_salary
    """ + FILTER_SQL + " GROUP BY j.jobtitle ORDER BY average_salary DESC, j.jobtitle LIMIT 10", params)
    fig = px.bar(by_title.sort_values("average_salary"), x="average_salary", y="job_title",
                 orientation="h", title="Top 10 job titles by average salary",
                 hover_data={"employees": True},
                 labels={"average_salary": "Average salary ($)",
                         "job_title": "Job title", "employees": "Employees"})
    st.plotly_chart(fig, width="stretch")

    # 6. Required expanded table.
    with st.expander("View employee table"):
        employees = run_query("""
            SELECT p.name, j.jobtitle AS job_title, d.departmentname AS department,
                   v.divtype AS division, e.salary
        """ + FILTER_SQL + " ORDER BY e.salary DESC, p.name", params)
        st.dataframe(employees, width="stretch", hide_index=True)
        st.caption(f"{len(employees):,} employees in current selection")
except Exception as exc:
    st.error("Dashboard query failed.")
    st.exception(exc)
