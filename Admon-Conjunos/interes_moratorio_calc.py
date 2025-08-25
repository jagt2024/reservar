import streamlit as st
import pandas as pd
from datetime import datetime, date
import numpy as np

def calcular_interes_moratorio(pago_principal, tasa_moratoria, dias_mora, año_base=360):
    """
    Calcula el interés moratorio sobre el pago principal de una cuota vencida.
    
    Parámetros:
    - pago_principal: Monto del pago principal de la cuota vencida
    - tasa_moratoria: Tasa de interés moratorio anual (en decimal, ej: 0.05 para 5%)
    - dias_mora: Número de días de mora
    - año_base: Días del año para el cálculo (default 360)
    
    Retorna:
    - Interés moratorio calculado
    """
    interes_moratorio = pago_principal * tasa_moratoria * (dias_mora / año_base)
    return interes_moratorio

def simulador_main():
    st.title("🧮 Calculadora de Interés Moratorio")
    st.markdown("---")
    
    # Configuración en sidebar
    st.sidebar.header("⚙️ Configuración")
    año_base = st.sidebar.selectbox(
        "Año base para cálculo",
        options=[360, 365],
        index=0,
        help="360 días es el estándar comercial, 365 días es el año calendario"
    )
    
    # Pestañas para diferentes modalidades de cálculo
    tab1, tab2, tab3 = st.tabs(["📊 Cálculo Individual", "📋 Cálculo Múltiple", "📈 Análisis por Períodos"])
    
    with tab1:
        st.subheader("Cálculo Individual de Interés Moratorio")
        
        col1, col2 = st.columns(2)
        
        with col1:
            pago_principal = st.number_input(
                "💰 Pago Principal ($)",
                min_value=0.0,
                value=1000.0,
                step=100.0,
                format="%.2f"
            )
            
            tasa_moratoria = st.number_input(
                "📊 Tasa de Interés Moratorio (% anual)",
                min_value=0.0,
                max_value=100.0,
                value=12.0,
                step=0.5,
                format="%.2f"
            )
        
        with col2:
            # Opción para calcular días automáticamente o ingresarlos manualmente
            modo_calculo = st.radio(
                "🗓️ Modo de cálculo de días",
                options=["Días específicos", "Calcular entre fechas"]
            )
            
            if modo_calculo == "Días específicos":
                dias_mora = st.number_input(
                    "📅 Días de mora",
                    min_value=0,
                    value=30,
                    step=1
                )
            else:
                col_fecha1, col_fecha2 = st.columns(2)
                with col_fecha1:
                    fecha_vencimiento = st.date_input(
                        "Fecha de vencimiento",
                        value=date(2024, 1, 1)
                    )
                with col_fecha2:
                    fecha_calculo = st.date_input(
                        "Fecha de cálculo",
                        value=date.today()
                    )
                
                dias_mora = (fecha_calculo - fecha_vencimiento).days
                if dias_mora < 0:
                    st.error("⚠️ La fecha de cálculo debe ser posterior a la fecha de vencimiento")
                    dias_mora = 0
                else:
                    st.info(f"📅 Días de mora calculados: {dias_mora}")
        
        # Cálculo
        tasa_decimal = tasa_moratoria / 100
        interes_moratorio = calcular_interes_moratorio(pago_principal, tasa_decimal, dias_mora, año_base)
        
        # Mostrar resultados
        st.markdown("---")
        st.subheader("📈 Resultados del Cálculo")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                label="💰 Pago Principal",
                value=f"${pago_principal:,.2f}"
            )
        
        with col2:
            st.metric(
                label="📊 Tasa Moratoria",
                value=f"{tasa_moratoria}% anual"
            )
        
        with col3:
            st.metric(
                label="📅 Días de Mora",
                value=f"{dias_mora} días"
            )
        
        with col4:
            st.metric(
                label="🔥 Interés Moratorio",
                value=f"${interes_moratorio:,.2f}",
                delta=f"{(interes_moratorio/pago_principal*100):,.2f}%" if pago_principal > 0 else None
            )
        
        # Fórmula utilizada
        st.markdown("---")
        st.subheader("📝 Fórmula Utilizada")
        st.latex(r"""
        Interés\ Moratorio = Pago\ Principal \times Tasa\ Moratoria \times \frac{Días\ de\ Mora}{""" + str(año_base) + r"""}
        """)
        
        st.code(f"""
        Interés Moratorio = ${pago_principal:,.2f} × {tasa_moratoria}% × ({dias_mora}/{año_base})
        Interés Moratorio = ${pago_principal:,.2f} × {tasa_decimal:.4f} × {dias_mora/año_base:.6f}
        Interés Moratorio = ${interes_moratorio:,.2f}
        """)
    
    with tab2:
        st.subheader("Cálculo Múltiple de Intereses Moratorios")
        
        # Configuración para múltiples cuotas
        col1, col2 = st.columns(2)
        
        with col1:
            tasa_moratoria_mult = st.number_input(
                "📊 Tasa de Interés Moratorio (% anual)",
                min_value=0.0,
                max_value=100.0,
                value=12.0,
                step=0.5,
                format="%.2f",
                key="tasa_mult"
            )
        
        with col2:
            num_cuotas = st.number_input(
                "📋 Número de cuotas a calcular",
                min_value=1,
                max_value=50,
                value=5,
                step=1
            )
        
        # Crear formulario para múltiples cuotas
        cuotas_data = []
        
        st.markdown("---")
        st.subheader("📊 Ingrese los datos de cada cuota:")
        
        for i in range(num_cuotas):
            with st.expander(f"Cuota {i+1}", expanded=(i < 3)):
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    principal = st.number_input(
                        f"💰 Pago Principal Cuota {i+1} ($)",
                        min_value=0.0,
                        value=1000.0,
                        step=100.0,
                        key=f"principal_{i}"
                    )
                
                with col2:
                    dias = st.number_input(
                        f"📅 Días de mora Cuota {i+1}",
                        min_value=0,
                        value=(i+1)*30,
                        step=1,
                        key=f"dias_{i}"
                    )
                
                with col3:
                    tasa_decimal_mult = tasa_moratoria_mult / 100
                    interes = calcular_interes_moratorio(principal, tasa_decimal_mult, dias, año_base)
                    st.metric(
                        f"🔥 Interés Cuota {i+1}",
                        f"${interes:,.2f}"
                    )
                
                cuotas_data.append({
                    'Cuota': i+1,
                    'Pago Principal': principal,
                    'Días Mora': dias,
                    'Interés Moratorio': interes,
                    'Total': principal + interes
                })
        
        # Crear DataFrame y mostrar tabla
        df_cuotas = pd.DataFrame(cuotas_data)
        
        st.markdown("---")
        st.subheader("📋 Resumen de Cálculos")
        
        # Formatear tabla
        df_display = df_cuotas.copy()
        df_display['Pago Principal'] = df_display['Pago Principal'].apply(lambda x: f"${x:,.2f}")
        df_display['Interés Moratorio'] = df_display['Interés Moratorio'].apply(lambda x: f"${x:,.2f}")
        df_display['Total'] = df_display['Total'].apply(lambda x: f"${x:,.2f}")
        
        st.dataframe(df_display, use_container_width=True)
        
        # Totales
        total_principal = df_cuotas['Pago Principal'].sum()
        total_interes = df_cuotas['Interés Moratorio'].sum()
        total_general = total_principal + total_interes
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("💰 Total Principal", f"${total_principal:,.2f}")
        
        with col2:
            st.metric("🔥 Total Intereses", f"${total_interes:,.2f}")
        
        with col3:
            st.metric("💵 Total General", f"${total_general:,.2f}")
    
    with tab3:
        st.subheader("Análisis de Interés Moratorio por Períodos")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            principal_analisis = st.number_input(
                "💰 Pago Principal ($)",
                min_value=0.0,
                value=5000.0,
                step=100.0,
                key="principal_analisis"
            )
        
        with col2:
            tasa_analisis = st.number_input(
                "📊 Tasa Moratoria (% anual)",
                min_value=0.0,
                max_value=100.0,
                value=18.0,
                step=0.5,
                key="tasa_analisis"
            )
        
        with col3:
            max_dias = st.number_input(
                "📅 Máximo días a analizar",
                min_value=30,
                max_value=720,
                value=365,
                step=30
            )
        
        # Generar datos para análisis
        dias_range = range(1, max_dias + 1, 7)  # Cada 7 días
        tasa_decimal_analisis = tasa_analisis / 100
        
        analisis_data = []
        for dias in dias_range:
            interes = calcular_interes_moratorio(principal_analisis, tasa_decimal_analisis, dias, año_base)
            porcentaje = (interes / principal_analisis) * 100 if principal_analisis > 0 else 0
            
            analisis_data.append({
                'Días': dias,
                'Interés Moratorio': interes,
                'Porcentaje del Principal': porcentaje,
                'Total Adeudado': principal_analisis + interes
            })
        
        df_analisis = pd.DataFrame(analisis_data)
        
        # Gráfico
        st.line_chart(
            df_analisis.set_index('Días')[['Interés Moratorio']],
            use_container_width=True
        )
        
        # Milestones importantes
        st.markdown("---")
        st.subheader("🎯 Hitos Importantes")
        
        milestones = [30, 60, 90, 180, 365]
        milestone_data = []
        
        for milestone in milestones:
            if milestone <= max_dias:
                interes = calcular_interes_moratorio(principal_analisis, tasa_decimal_analisis, milestone, año_base)
                porcentaje = (interes / principal_analisis) * 100 if principal_analisis > 0 else 0
                milestone_data.append({
                    'Período': f"{milestone} días",
                    'Interés Moratorio': f"${interes:,.2f}",
                    '% del Principal': f"{porcentaje:.2f}%",
                    'Total': f"${principal_analisis + interes:,.2f}"
                })
        
        df_milestones = pd.DataFrame(milestone_data)
        st.dataframe(df_milestones, use_container_width=True)

if __name__ == "__main__":
    simulador_main()
