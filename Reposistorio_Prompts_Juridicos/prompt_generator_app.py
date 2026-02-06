#!/usr/bin/env python3
"""
Aplicación Streamlit para generar prompts estructurados de alta calidad.
"""

import streamlit as st
import json
from typing import Dict, List


class PromptGenerator:
    """Generador de prompts usando frameworks establecidos."""
    
    FRAMEWORKS = {
        "CTF": ["CONTEXT", "TASK", "FORMAT"],
        "RISEN": ["ROLE", "INSTRUCTIONS", "STEPS", "END GOAL", "NARROWING"],
        "RACE": ["ROLE", "ACTION", "CONTEXT", "EXPECTATION"],
        "CRAFT": ["CONTEXT", "ROLE", "ACTION", "FORMAT", "TARGET"],
        "SMART": ["SPECIFIC", "MEASURABLE", "ACHIEVABLE", "RELEVANT", "TIME-BOUND"],
        "APE": ["ACTION", "PURPOSE", "EXPECTATION"],
        "STAR": ["SITUATION", "TASK", "ACTION", "RESULT"],
        "CREATE": ["CHARACTER", "REQUEST", "EXAMPLES", "ADJUSTMENTS", "TYPE", "EXTRAS"]
    }
    
    FRAMEWORK_DESCRIPTIONS = {
        "CTF": "Context-Task-Format: Simple y efectivo para tareas claras",
        "RISEN": "Role-Instructions-Steps-End goal-Narrowing: Completo y estructurado",
        "RACE": "Role-Action-Context-Expectation: Enfocado en resultados",
        "CRAFT": "Context-Role-Action-Format-Target: Balanceado y profesional",
        "SMART": "Specific-Measurable-Achievable-Relevant-Time-bound: Para objetivos claros",
        "APE": "Action-Purpose-Expectation: Directo y conciso",
        "STAR": "Situation-Task-Action-Result: Narrativo y orientado a resultados",
        "CREATE": "Character-Request-Examples-Adjustments-Type-Extras: Para contenido creativo"
    }
    
    def use_framework(self, framework: str) -> Dict[str, str]:
        """Retorna una plantilla del framework seleccionado."""
        if framework.upper() not in self.FRAMEWORKS:
            available = ", ".join(self.FRAMEWORKS.keys())
            raise ValueError(f"Framework '{framework}' no disponible. Usa uno de: {available}")
        
        components = self.FRAMEWORKS[framework.upper()]
        template = {}
        for component in components:
            template[component] = f"[Completa {component}]"
        
        return template
    
    def generate_prompt(self, framework: str, components: Dict[str, str]) -> str:
        """Genera un prompt estructurado usando el framework especificado."""
        framework_upper = framework.upper()
        if framework_upper not in self.FRAMEWORKS:
            raise ValueError(f"Framework '{framework}' no reconocido")
        
        prompt_parts = []
        for key in self.FRAMEWORKS[framework_upper]:
            if key in components and components[key].strip():
                prompt_parts.append(f"**{key}:**\n{components[key]}")
        
        return "\n\n".join(prompt_parts)
    
    def add_techniques(self, base_prompt: str, techniques: List[str]) -> str:
        """Añade técnicas de prompting al prompt base."""
        enhanced_prompt = base_prompt
        
        if "Chain of Thought" in techniques:
            enhanced_prompt += "\n\n---\n**TÉCNICA APLICADA: Chain of Thought**\n[Muestra tu razonamiento paso a paso antes de dar la respuesta final]"
        
        if "Few-Shot Learning" in techniques:
            enhanced_prompt += "\n\n---\n**TÉCNICA APLICADA: Few-Shot Learning**\n[Incluye 2-3 ejemplos específicos antes de ejecutar la tarea principal]"
        
        if "Self-Consistency" in techniques:
            enhanced_prompt += "\n\n---\n**TÉCNICA APLICADA: Self-Consistency**\n[Genera múltiples enfoques diferentes y selecciona el mejor resultado]"
        
        if "Meta-Prompting" in techniques:
            enhanced_prompt = f"**TÉCNICA APLICADA: Meta-Prompting**\n[Primero optimiza este prompt para máxima efectividad, luego ejecútalo]\n\n---\n\n{enhanced_prompt}"
        
        if "Zero-Shot CoT" in techniques:
            enhanced_prompt += "\n\n---\n**TÉCNICA APLICADA: Zero-Shot CoT**\n[Piensa paso a paso para resolver esto]"
        
        return enhanced_prompt
    
    def validate_prompt(self, prompt: str) -> Dict[str, any]:
        """Valida la calidad de un prompt usando criterios establecidos."""
        validation = {
            "has_clear_objective": len(prompt) > 50,
            "has_structure": "\n" in prompt,
            "has_specific_format": "FORMAT" in prompt.upper() or "OUTPUT" in prompt.upper(),
            "has_context": "CONTEXT" in prompt.upper() or "BACKGROUND" in prompt.upper() or "SITUATION" in prompt.upper(),
            "has_role": "ROLE" in prompt.upper() or "ACT AS" in prompt.upper() or "CHARACTER" in prompt.upper(),
            "length_appropriate": 100 < len(prompt) < 5000,
            "score": 0
        }
        
        validation["score"] = sum([
            validation["has_clear_objective"],
            validation["has_structure"],
            validation["has_specific_format"],
            validation["has_context"],
            validation["has_role"],
            validation["length_appropriate"]
        ]) / 6 * 100
        
        return validation


def main():
    """Aplicación principal de Streamlit."""
    st.set_page_config(
        page_title="Generador de Prompts Profesional",
        page_icon="🎯",
        layout="wide"
    )
    
    st.title("🎯 Generador de Prompts Estructurados")
    st.markdown("*Crea prompts de alta calidad usando frameworks probados y técnicas avanzadas*")
    
    generator = PromptGenerator()
    
    # Sidebar para configuración
    with st.sidebar:
        st.header("⚙️ Configuración")
        
        # Selección de framework
        selected_framework = st.selectbox(
            "Selecciona un Framework",
            options=list(generator.FRAMEWORKS.keys()),
            format_func=lambda x: f"{x} - {generator.FRAMEWORK_DESCRIPTIONS[x]}"
        )
        
        st.info(f"**Componentes:** {', '.join(generator.FRAMEWORKS[selected_framework])}")
        
        # Selección de técnicas
        st.subheader("🔧 Técnicas de Prompting")
        techniques = st.multiselect(
            "Selecciona técnicas a aplicar",
            options=[
                "Chain of Thought",
                "Few-Shot Learning",
                "Self-Consistency",
                "Meta-Prompting",
                "Zero-Shot CoT"
            ],
            help="Selecciona una o más técnicas para mejorar tu prompt"
        )
        
        st.markdown("---")
        st.markdown("### 📚 Guía Rápida")
        st.markdown("""
        **Chain of Thought:** Razonamiento paso a paso
        
        **Few-Shot:** Aprendizaje por ejemplos
        
        **Self-Consistency:** Múltiples enfoques
        
        **Meta-Prompting:** Auto-optimización
        
        **Zero-Shot CoT:** Pensamiento sin ejemplos
        """)
    
    # Área principal
    tab1, tab2, tab3 = st.tabs(["📝 Crear Prompt", "🔍 Validar Prompt", "📖 Plantilla"])
    
    with tab1:
        st.header("Construye tu Prompt")
        
        components = {}
        framework_components = generator.FRAMEWORKS[selected_framework]
        
        # Crear campos para cada componente del framework
        col1, col2 = st.columns(2)
        
        for idx, component in enumerate(framework_components):
            with col1 if idx % 2 == 0 else col2:
                components[component] = st.text_area(
                    f"{component}",
                    height=100,
                    placeholder=f"Describe el {component.lower()} de tu prompt...",
                    key=f"component_{component}"
                )
        
        st.markdown("---")
        
        if st.button("🚀 Generar Prompt", type="primary", use_container_width=True):
            if not any(components.values()):
                st.error("⚠️ Por favor, completa al menos un componente del framework")
            else:
                # Generar prompt base
                base_prompt = generator.generate_prompt(selected_framework, components)
                
                # Aplicar técnicas si fueron seleccionadas
                if techniques:
                    final_prompt = generator.add_techniques(base_prompt, techniques)
                else:
                    final_prompt = base_prompt
                
                # Validar prompt
                validation = generator.validate_prompt(final_prompt)
                
                # Mostrar resultados
                st.success("✅ Prompt generado exitosamente!")
                
                # Mostrar prompt en un contenedor expandible
                with st.expander("📄 Prompt Final", expanded=True):
                    st.markdown(final_prompt)
                    st.download_button(
                        label="💾 Descargar Prompt",
                        data=final_prompt,
                        file_name=f"prompt_{selected_framework.lower()}.txt",
                        mime="text/plain"
                    )
                
                # Mostrar validación
                st.subheader("📊 Validación de Calidad")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    score_color = "green" if validation["score"] >= 70 else "orange" if validation["score"] >= 50 else "red"
                    st.metric("Score de Calidad", f"{validation['score']:.1f}%")
                
                with col2:
                    st.metric("Longitud", f"{len(final_prompt)} caracteres")
                
                with col3:
                    passed = sum([v for k, v in validation.items() if k != "score"])
                    st.metric("Criterios Cumplidos", f"{passed}/6")
                
                # Detalles de validación
                st.markdown("#### Criterios de Validación")
                
                criteria_cols = st.columns(2)
                criteria = [
                    ("Objetivo Claro", "has_clear_objective", "Más de 50 caracteres"),
                    ("Estructura", "has_structure", "Contiene saltos de línea"),
                    ("Formato Específico", "has_specific_format", "Define formato de salida"),
                    ("Contexto", "has_context", "Incluye contexto o situación"),
                    ("Rol Definido", "has_role", "Especifica un rol o personaje"),
                    ("Longitud Apropiada", "length_appropriate", "Entre 100 y 5000 caracteres")
                ]
                
                for idx, (name, key, description) in enumerate(criteria):
                    with criteria_cols[idx % 2]:
                        if validation[key]:
                            st.success(f"✅ {name}")
                        else:
                            st.error(f"❌ {name}")
                        st.caption(description)
                
                # Recomendaciones
                if validation["score"] < 70:
                    st.warning("💡 **Recomendaciones para mejorar:**")
                    if not validation["has_context"]:
                        st.markdown("- Añade más contexto o background a tu prompt")
                    if not validation["has_role"]:
                        st.markdown("- Define un rol específico para el asistente")
                    if not validation["has_specific_format"]:
                        st.markdown("- Especifica el formato de salida deseado")
                    if not validation["length_appropriate"]:
                        st.markdown("- Ajusta la longitud del prompt (100-5000 caracteres)")
    
    with tab2:
        st.header("Validar Prompt Existente")
        st.markdown("Pega un prompt existente para validar su calidad")
        
        existing_prompt = st.text_area(
            "Prompt a validar",
            height=300,
            placeholder="Pega aquí tu prompt para validarlo..."
        )
        
        if st.button("🔍 Validar", type="primary"):
            if existing_prompt.strip():
                validation = generator.validate_prompt(existing_prompt)
                
                st.subheader("📊 Resultados de Validación")
                
                # Métricas principales
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    score = validation["score"]
                    if score >= 80:
                        st.success(f"**Excelente:** {score:.1f}%")
                    elif score >= 60:
                        st.warning(f"**Bueno:** {score:.1f}%")
                    else:
                        st.error(f"**Mejorable:** {score:.1f}%")
                
                with col2:
                    st.info(f"**Longitud:** {len(existing_prompt)} caracteres")
                
                with col3:
                    passed = sum([v for k, v in validation.items() if k != "score"])
                    st.info(f"**Criterios:** {passed}/6")
                
                # Barra de progreso
                st.progress(validation["score"] / 100)
                
                # Detalles
                st.markdown("#### Análisis Detallado")
                
                details = {
                    "✅ Objetivo Claro": validation["has_clear_objective"],
                    "✅ Estructura": validation["has_structure"],
                    "✅ Formato Específico": validation["has_specific_format"],
                    "✅ Contexto": validation["has_context"],
                    "✅ Rol Definido": validation["has_role"],
                    "✅ Longitud Apropiada": validation["length_appropriate"]
                }
                
                for criterion, passed in details.items():
                    if passed:
                        st.success(criterion)
                    else:
                        st.error(criterion.replace("✅", "❌"))
                
                # JSON de validación
                with st.expander("📋 Ver JSON de Validación"):
                    st.json(validation)
            else:
                st.warning("⚠️ Por favor, ingresa un prompt para validar")
    
    with tab3:
        st.header("Plantilla del Framework")
        st.markdown(f"**Framework seleccionado:** {selected_framework}")
        st.info(generator.FRAMEWORK_DESCRIPTIONS[selected_framework])
        
        template = generator.use_framework(selected_framework)
        
        st.subheader("Componentes del Framework")
        
        for component, placeholder in template.items():
            st.markdown(f"**{component}**")
            st.text(placeholder)
            st.markdown("---")
        
        # Exportar plantilla
        template_text = "\n\n".join([f"{k}:\n{v}\n" for k, v in template.items()])
        
        st.download_button(
            label="💾 Descargar Plantilla",
            data=template_text,
            file_name=f"plantilla_{selected_framework.lower()}.txt",
            mime="text/plain",
            use_container_width=True
        )
        
        # Comparación de frameworks
        with st.expander("🔄 Comparar Frameworks"):
            st.markdown("### Todos los Frameworks Disponibles")
            
            for fw_name, fw_components in generator.FRAMEWORKS.items():
                st.markdown(f"**{fw_name}:** {generator.FRAMEWORK_DESCRIPTIONS[fw_name]}")
                st.caption(f"Componentes: {', '.join(fw_components)}")
                st.markdown("")


if __name__ == "__main__":
    main()
