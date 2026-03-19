from pathlib import Path
import json

import pandas as pd
import plotly.express as px
import pydeck as pdk
import streamlit as st


APP_DIR = Path(__file__).resolve().parent
DASH_DIR = APP_DIR

st.set_page_config(
    page_title="Cierre de Cartera Agrícola",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)


def fmt_int(x: float | int | None) -> str:
    if x is None or pd.isna(x):
        return "-"
    return f"{int(round(float(x))):,}".replace(",", ".")


def fmt_num(x: float | int | None, decimals: int = 1) -> str:
    if x is None or pd.isna(x):
        return "-"
    return f"{float(x):,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")


@st.cache_data
def load_csv(path):
    return pd.read_csv(path)


@st.cache_data
def safe_read_csv(path):
    path = Path(path)
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame()


@st.cache_data
def load_all():
    with open(DASH_DIR / "dashboard_kpis.json", "r", encoding="utf-8") as f:
        kpis = json.load(f)

    return {
        "points": load_csv(DASH_DIR / "dashboard_points.csv"),
        "cultivo": load_csv(DASH_DIR / "dashboard_cultivo.csv"),
        "provincia": load_csv(DASH_DIR / "dashboard_provincia.csv"),
        "depto": load_csv(DASH_DIR / "dashboard_depto.csv"),
        "asegurado": load_csv(DASH_DIR / "dashboard_asegurado.csv"),
        "qc_campos": safe_read_csv(DASH_DIR / "perfil_calidad_campos.csv"),
        "dup_business": safe_read_csv(DASH_DIR / "duplicados_negocio.csv"),
        "dup_exact": safe_read_csv(DASH_DIR / "duplicados_exactos.csv"),
        "kpis": kpis,
    }


def filter_points(df: pd.DataFrame) -> pd.DataFrame:
    st.sidebar.header("Filtros")

    provincias = sorted(df["provincia_std"].dropna().astype(str).unique().tolist())
    cultivos = sorted(df["cultivo_std"].dropna().astype(str).unique().tolist())
    monedas = sorted(df["moneda_std"].dropna().astype(str).unique().tolist())
    asegurados = sorted(df["asegurado_std"].dropna().astype(str).unique().tolist())

    prov_sel = st.sidebar.multiselect("Provincia", provincias)
    cultivo_sel = st.sidebar.multiselect("Cultivo", cultivos)
    moneda_sel = st.sidebar.multiselect("Moneda", monedas)
    asegurado_sel = st.sidebar.multiselect("Asegurado", asegurados)
    review_sel = st.sidebar.selectbox(
        "Revisión",
        options=["Todos", "Solo needs_review", "Solo OK"],
        index=0,
    )

    has_max = float(df["has"].fillna(0).max()) if not df.empty else 1.0
    has_range = st.sidebar.slider(
        "Rango hectáreas",
        min_value=0.0,
        max_value=max(1.0, has_max),
        value=(0.0, max(1.0, has_max)),
        step=1.0,
    )

    filtered = df.copy()

    if prov_sel:
        filtered = filtered[filtered["provincia_std"].isin(prov_sel)]
    if cultivo_sel:
        filtered = filtered[filtered["cultivo_std"].isin(cultivo_sel)]
    if moneda_sel:
        filtered = filtered[filtered["moneda_std"].isin(moneda_sel)]
    if asegurado_sel:
        filtered = filtered[filtered["asegurado_std"].isin(asegurado_sel)]

    filtered = filtered[filtered["has"].fillna(0).between(has_range[0], has_range[1])]

    if review_sel == "Solo needs_review":
        filtered = filtered[filtered["needs_review"] == True]
    elif review_sel == "Solo OK":
        filtered = filtered[filtered["needs_review"] != True]

    st.sidebar.markdown("---")
    st.sidebar.caption(f"Registros visibles: {len(filtered):,}".replace(",", "."))
    return filtered


def filtered_summary(df: pd.DataFrame) -> dict:
    usd = df.loc[df["moneda_std"] == "USD", "suma_asegurada"].sum()
    ars = df.loc[df["moneda_std"] == "ARS", "suma_asegurada"].sum()
    return {
        "n_registros": int(len(df)),
        "n_asegurados": int(df["asegurado_std"].nunique()) if not df.empty else 0,
        "n_provincias": int(df["provincia_std"].nunique()) if not df.empty else 0,
        "hectareas": float(df["has"].sum()) if not df.empty else 0.0,
        "pct_geo": float(df["coord_ok"].mean()) if len(df) else 0.0,
        "suma_ars": float(ars),
        "suma_usd": float(usd),
    }


def extra_summary(df: pd.DataFrame) -> dict:
    if df.empty:
        return {
            "pct_review": 0.0,
            "ha_promedio": 0.0,
            "ha_mediana": 0.0,
            "share_top5_aseg": 0.0,
            "share_top5_prov": 0.0,
            "cultivo_top": "-",
            "cultivo_top_share": 0.0,
        }

    total_has = df["has"].fillna(0).sum()

    top5_aseg = (
        df.groupby("asegurado_std")["has"]
        .sum()
        .sort_values(ascending=False)
        .head(5)
        .sum()
    )

    top5_prov = (
        df.groupby("provincia_std")["has"]
        .sum()
        .sort_values(ascending=False)
        .head(5)
        .sum()
    )

    cultivo_rank = (
        df.groupby("cultivo_std")["has"]
        .sum()
        .sort_values(ascending=False)
    )

    cultivo_top = cultivo_rank.index[0] if len(cultivo_rank) else "-"
    cultivo_top_share = (cultivo_rank.iloc[0] / total_has) if total_has > 0 and len(cultivo_rank) else 0.0

    return {
        "pct_review": float(df["needs_review"].fillna(False).mean()),
        "ha_promedio": float(df["has"].fillna(0).mean()),
        "ha_mediana": float(df["has"].fillna(0).median()),
        "share_top5_aseg": float(top5_aseg / total_has) if total_has > 0 else 0.0,
        "share_top5_prov": float(top5_prov / total_has) if total_has > 0 else 0.0,
        "cultivo_top": cultivo_top,
        "cultivo_top_share": float(cultivo_top_share),
    }


def card(title: str, value: str, help_text: str | None = None) -> None:
    st.markdown(
        f"""
        <div style="padding:14px;border:1px solid #e5e7eb;border-radius:16px;background:#ffffff;">
            <div style="font-size:0.85rem;color:#6b7280;">{title}</div>
            <div style="font-size:1.55rem;font-weight:700;">{value}</div>
            <div style="font-size:0.75rem;color:#6b7280;">{help_text or ''}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    data = load_all()
    points = data["points"].copy()
    qc_campos = data.get("qc_campos", pd.DataFrame()).copy()
    dup_business = data.get("dup_business", pd.DataFrame()).copy()
    dup_exact = data.get("dup_exact", pd.DataFrame()).copy()
    global_kpis = data["kpis"]

    points["needs_review"] = points["needs_review"].fillna(False)
    points["coord_ok"] = points["coord_ok"].fillna(False)

    st.title("🌾 Dashboard de cierre de cartera agrícola")
    st.caption("Base orientada a cierre de campaña, exposición, concentración y control de calidad.")

    filtered = filter_points(points)
    summary = filtered_summary(filtered)
    extra = extra_summary(filtered)

    tabs = st.tabs(["Resumen", "Mapa", "Concentración", "Calidad", "Datos"])

    with tabs[0]:
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        with c1:
            card("Registros", fmt_int(summary["n_registros"]))
        with c2:
            card("Asegurados", fmt_int(summary["n_asegurados"]))
        with c3:
            card("Provincias", fmt_int(summary["n_provincias"]))
        with c4:
            card("Hectáreas", fmt_num(summary["hectareas"], 1))
        with c5:
            card("Suma ARS", fmt_num(summary["suma_ars"], 0))
        with c6:
            card("Suma USD", fmt_num(summary["suma_usd"], 0))

        st.markdown("### KPIs complementarios")
        k1, k2, k3, k4 = st.columns(4)
        with k1:
            card("% needs_review", f"{extra['pct_review']*100:.1f}%")
        with k2:
            card("Ha promedio / registro", fmt_num(extra["ha_promedio"], 1))
        with k3:
            card("Ha mediana / registro", fmt_num(extra["ha_mediana"], 1))
        with k4:
            card("Cultivo líder", f"{extra['cultivo_top']} ({extra['cultivo_top_share']*100:.1f}%)")

        k5, k6 = st.columns(2)
        with k5:
            st.metric("Share top 5 asegurados", f"{extra['share_top5_aseg']*100:.1f}%")
        with k6:
            st.metric("Share top 5 provincias", f"{extra['share_top5_prov']*100:.1f}%")

        st.markdown("### Lectura ejecutiva")
        e1, e2, e3 = st.columns(3)
        with e1:
            st.metric(
                "Georreferencia válida",
                f"{summary['pct_geo']*100:.1f}%",
                help="Porcentaje de registros filtrados con coordenadas válidas.",
            )
        with e2:
            st.metric(
                "Top 10 asegurados / ha (global)",
                f"{global_kpis['concentration']['share_top10_asegurados_has']*100:.1f}%",
            )
        with e3:
            st.metric(
                "Top 10 deptos / ha (global)",
                f"{global_kpis['concentration']['share_top10_deptos_has']*100:.1f}%",
            )

        col_a, col_b = st.columns(2)

        top_cultivos = (
            filtered.groupby("cultivo_std", dropna=False, as_index=False)
            .agg(hectareas=("has", "sum"), registros=("it", "count"))
            .sort_values("hectareas", ascending=False)
            .head(10)
        )
        with col_a:
            fig = px.bar(
                top_cultivos,
                x="hectareas",
                y="cultivo_std",
                orientation="h",
                title="Top cultivos por hectáreas",
                text_auto=".2s",
            )
            fig.update_layout(height=420, yaxis_title=None, xaxis_title="Hectáreas")
            st.plotly_chart(fig, use_container_width=True)

        top_provincias = (
            filtered.groupby("provincia_std", dropna=False, as_index=False)
            .agg(hectareas=("has", "sum"), registros=("it", "count"))
            .sort_values("hectareas", ascending=False)
            .head(10)
        )
        with col_b:
            fig = px.bar(
                top_provincias,
                x="hectareas",
                y="provincia_std",
                orientation="h",
                title="Top provincias por hectáreas",
                text_auto=".2s",
            )
            fig.update_layout(height=420, yaxis_title=None, xaxis_title="Hectáreas")
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("### Mix de hectáreas por cultivo")
        mix_cultivo = (
            filtered.groupby("cultivo_std", as_index=False)
            .agg(hectareas=("has", "sum"))
            .sort_values("hectareas", ascending=False)
        )
        if not mix_cultivo.empty:
            fig = px.pie(
                mix_cultivo,
                names="cultivo_std",
                values="hectareas",
                hole=0.45,
                title="Mix de hectáreas por cultivo",
            )
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("### Top asegurados")
        top_aseg = (
            filtered.groupby("asegurado_std", as_index=False)
            .agg(
                hectareas=("has", "sum"),
                registros=("it", "count"),
                provincias=("provincia_std", "nunique"),
            )
            .sort_values("hectareas", ascending=False)
            .head(15)
        )
        st.dataframe(top_aseg, use_container_width=True, hide_index=True)

    with tabs[1]:
        st.markdown("### Mapa de cartera")
        geo = filtered[
            (filtered["coord_ok"] == True)
            & filtered["latitud"].notna()
            & filtered["longitud"].notna()
        ].copy()

        st.caption("El mapa usa los puntos con coordenadas válidas del filtro actual.")

        if geo.empty:
            st.warning("No hay puntos georreferenciados para el filtro seleccionado.")
        else:
            geo_map = geo.rename(columns={"latitud": "lat", "longitud": "lon"})[["lat", "lon"]]
            st.map(geo_map, use_container_width=True)

            st.markdown("### Mapa de burbujas por hectáreas")
            geo_bubble = geo.copy()
            geo_bubble["radius"] = geo_bubble["has"].fillna(0).clip(lower=1) * 8

            view_state = pdk.ViewState(
                latitude=float(geo_bubble["latitud"].mean()),
                longitude=float(geo_bubble["longitud"].mean()),
                zoom=4.2,
                pitch=0,
            )

            bubble_layer = pdk.Layer(
                "ScatterplotLayer",
                data=geo_bubble,
                get_position="[longitud, latitud]",
                get_radius="radius",
                get_fill_color="[34, 139, 34, 120]",
                pickable=True,
            )

            tooltip = {
                "html": """
                <b>IT:</b> {it} <br/>
                <b>Asegurado:</b> {asegurado_std} <br/>
                <b>Provincia:</b> {provincia_std} <br/>
                <b>Cultivo:</b> {cultivo_std} <br/>
                <b>Has:</b> {has} <br/>
                <b>Moneda:</b> {moneda_std}
                """,
                "style": {"backgroundColor": "white", "color": "black"},
            }

            st.pydeck_chart(
                pdk.Deck(
                    layers=[bubble_layer],
                    initial_view_state=view_state,
                    tooltip=tooltip,
                ),
                use_container_width=True,
            )

            st.markdown("### Mapa de densidad de cartera")
            heat_layer = pdk.Layer(
                "HeatmapLayer",
                data=geo,
                get_position="[longitud, latitud]",
                get_weight="has",
                radiusPixels=35,
            )

            st.pydeck_chart(
                pdk.Deck(
                    layers=[heat_layer],
                    initial_view_state=view_state,
                ),
                use_container_width=True,
            )

            map_col1, map_col2 = st.columns([1.2, 1])
            with map_col1:
                puntos_geo = geo[[
                    "it", "asegurado_std", "provincia_std", "depto_std", "localidad_std",
                    "cultivo_std", "has", "moneda_std", "suma_asegurada", "latitud", "longitud",
                ]].sort_values("has", ascending=False)
                st.dataframe(puntos_geo.head(200), use_container_width=True, hide_index=True)

            with map_col2:
                bubble = (
                    geo.groupby(["provincia_std", "depto_std"], as_index=False)
                    .agg(hectareas=("has", "sum"), registros=("it", "count"))
                    .sort_values("hectareas", ascending=False)
                    .head(20)
                )
                fig = px.bar(
                    bubble,
                    x="hectareas",
                    y="depto_std",
                    color="provincia_std",
                    orientation="h",
                    title="Departamentos con mayor exposición",
                )
                fig.update_layout(height=600, yaxis_title=None, xaxis_title="Hectáreas")
                st.plotly_chart(fig, use_container_width=True)

    with tabs[2]:
        st.markdown("### Concentración")
        c_left, c_right = st.columns(2)

        dep = (
            filtered.groupby(["provincia_std", "depto_std"], as_index=False)
            .agg(hectareas=("has", "sum"), asegurados=("asegurado_std", "nunique"))
            .sort_values("hectareas", ascending=False)
            .head(15)
        )
        with c_left:
            fig = px.bar(
                dep,
                x="hectareas",
                y="depto_std",
                color="provincia_std",
                orientation="h",
                title="Top departamentos",
            )
            fig.update_layout(height=500, yaxis_title=None, xaxis_title="Hectáreas")
            st.plotly_chart(fig, use_container_width=True)

        aseg = (
            filtered.groupby("asegurado_std", as_index=False)
            .agg(hectareas=("has", "sum"), provincias=("provincia_std", "nunique"), registros=("it", "count"))
            .sort_values("hectareas", ascending=False)
            .head(15)
        )
        with c_right:
            fig = px.bar(
                aseg,
                x="hectareas",
                y="asegurado_std",
                orientation="h",
                title="Top asegurados",
            )
            fig.update_layout(height=500, yaxis_title=None, xaxis_title="Hectáreas")
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("### Mix monetario por cultivo")
        mix = (
            filtered.pivot_table(
                index="cultivo_std",
                columns="moneda_std",
                values="suma_asegurada",
                aggfunc="sum",
                fill_value=0,
            )
            .reset_index()
        )
        if not mix.empty:
            melted = mix.melt(id_vars="cultivo_std", var_name="moneda", value_name="suma_asegurada")
            fig = px.bar(
                melted,
                x="cultivo_std",
                y="suma_asegurada",
                color="moneda",
                title="Suma asegurada por cultivo y moneda",
            )
            fig.update_layout(height=420, xaxis_title=None, yaxis_title="Suma asegurada")
            st.plotly_chart(fig, use_container_width=True)

    with tabs[3]:
        st.markdown("### Calidad de datos")
        q1, q2, q3 = st.columns(3)
        with q1:
            st.metric("Campos auditados", fmt_int(len(qc_campos)))
        with q2:
            st.metric("Duplicados exactos", fmt_int(len(dup_exact)))
        with q3:
            st.metric("Duplicados de negocio", fmt_int(len(dup_business)))

        left, right = st.columns([1, 1.2])
        with left:
            if qc_campos.empty:
                st.info("No se cargó archivo de perfil de calidad de campos.")
            else:
                st.dataframe(qc_campos, use_container_width=True, hide_index=True)

        with right:
            needs_review = filtered[filtered["needs_review"] == True].copy()
            st.markdown("#### Registros marcados para revisión")
            if needs_review.empty:
                st.success("Con el filtro actual no hay registros marcados para revisión.")
            else:
                st.dataframe(needs_review.head(200), use_container_width=True, hide_index=True)

    with tabs[4]:
        st.markdown("### Descarga y vista de datos")
        st.download_button(
            "Descargar puntos filtrados (CSV)",
            data=filtered.to_csv(index=False).encode("utf-8-sig"),
            file_name="dashboard_points_filtrado.csv",
            mime="text/csv",
        )
        st.dataframe(filtered.head(500), use_container_width=True, hide_index=True)

        with st.expander("Ver KPIs globales crudos"):
            st.json(global_kpis)


if __name__ == "__main__":
    main()
