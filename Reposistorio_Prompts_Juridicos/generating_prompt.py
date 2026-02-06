#!/usr/bin/env python3
"""
Script para generar prompts estructurados de alta calidad.
"""

import json
from typing import Dict, List, Optional


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
    
    def __init__(self):
        self.components = {}
        
    def use_framework(self, framework: str) -> Dict[str, str]:
        """
        Retorna una plantilla del framework seleccionado.
        """
        if framework.upper() not in self.FRAMEWORKS:
            available = ", ".join(self.FRAMEWORKS.keys())
            raise ValueError(f"Framework '{framework}' no disponible. Usa uno de: {available}")
        
        components = self.FRAMEWORKS[framework.upper()]
        template = {}
        for component in components:
            template[component] = f"[Completa {component}]"
        
        return template
    
    def generate_prompt(self, framework: str, components: Dict[str, str]) -> str:
        """
        Genera un prompt estructurado usando el framework especificado.
        """
        framework_upper = framework.upper()
        if framework_upper not in self.FRAMEWORKS:
            raise ValueError(f"Framework '{framework}' no reconocido")
        
        prompt_parts = []
        for key in self.FRAMEWORKS[framework_upper]:
            if key in components:
                prompt_parts.append(f"{key}: {components[key]}")
        
        return "\n\n".join(prompt_parts)
    
    def add_techniques(self, base_prompt: str, techniques: List[str]) -> str:
        """
        Añade técnicas de prompting al prompt base.
        """
        enhanced_prompt = base_prompt
        
        if "chain_of_thought" in techniques:
            enhanced_prompt += "\n\n[Muestra tu razonamiento paso a paso]"
        
        if "few_shot" in techniques:
            enhanced_prompt += "\n\n[Incluye 2-3 ejemplos antes de la tarea]"
        
        if "self_consistency" in techniques:
            enhanced_prompt += "\n\n[Genera múltiples enfoques y selecciona el mejor]"
        
        if "meta_prompting" in techniques:
            enhanced_prompt = f"Optimiza este prompt y luego ejecútalo:\n{enhanced_prompt}"
        
        return enhanced_prompt
    
    def validate_prompt(self, prompt: str) -> Dict[str, any]:
        """
        Valida la calidad de un prompt usando criterios establecidos.
        """
        validation = {
            "has_clear_objective": len(prompt) > 50,
            "has_structure": "\n" in prompt,
            "has_specific_format": "FORMAT" in prompt.upper() or "OUTPUT" in prompt.upper(),
            "has_context": "CONTEXT" in prompt.upper() or "BACKGROUND" in prompt.upper(),
            "has_role": "ROLE" in prompt.upper() or "ACT AS" in prompt.upper(),
            "length_appropriate": 100 < len(prompt) < 2000,
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
    """Ejemplo de uso del generador de prompts."""
    generator = PromptGenerator()
    
    # Ejemplo con framework RISEN
    components = {
        "ROLE": "Actúa como un experto en marketing digital con 10 años de experiencia.",
        "INSTRUCTIONS": "Crea una estrategia de contenido para redes sociales.",
        "STEPS": "1. Analiza el público objetivo\n2. Define pilares de contenido\n3. Crea calendario\n4. Establece KPIs",
        "END GOAL": "Un plan de contenido de 30 días listo para implementar.",
        "NARROWING": "Enfócate en Instagram y TikTok, audiencia 18-35 años, marca de moda sostenible."
    }
    
    prompt = generator.generate_prompt("RISEN", components)
    print("=== PROMPT GENERADO ===\n")
    print(prompt)
    print("\n=== VALIDACIÓN ===\n")
    
    validation = generator.validate_prompt(prompt)
    print(json.dumps(validation, indent=2))
    print(f"\nScore de calidad: {validation['score']:.1f}%")


if __name__ == "__main__":
    main()