def extract_resume_data(pdf_text):
    """Extraer todos los datos del CV para uso en las pestañas"""
    identificacion = extract_identification(pdf_text)
    nombres = extract_name(pdf_text)
    edad = extract_age(pdf_text)
    experiencia = extract_experience(pdf_text)
    
    # Extraer información de trabajos completa
    job_info, all_jobs = extract_job_info(pdf_text)
    
    # Verificar que job_info contiene toda la información necesaria
    if isinstance(job_info, dict):
        cargo = job_info.get("cargo", "")
        empresa = job_info.get("empresa", "")
        fecha_desde = job_info.get("fecha_desde", "")
        fecha_hasta = job_info.get("fecha_hasta", "")
        responsabilidades = job_info.get("responsabilidades", "")
        logros = job_info.get("logros", "")
    else:
        cargo, empresa, fecha_desde, fecha_hasta, responsabilidades, logros = "", "", "", "", "", ""
    
    # Extraer información educativa completa
    main_education, all_education = extract_education(pdf_text)
    
    # Extraer habilidades con nivel de competencia
    skills = extract_skills(pdf_text)
    
    # Extraer información de contacto detallada
    telefono, email, ciudad, linkedin, otras_redes = extract_contact_info(pdf_text)
    
    # Extraer perfil profesional completo
    perfil = extract_professional_profile(pdf_text)
    
    # Extraer idiomas y nivel
    idiomas = extract_languages(pdf_text)
    
    # Extraer certificaciones
    certificaciones = extract_certifications(pdf_text)
   
    return {
        "identificacion": identificacion,
        "nombres": nombres,
        "edad": edad,
        "experiencia": experiencia,
        "cargo": cargo,
        "empresa": empresa,
        "perfil_profesional": perfil,
        "fecha_desde": fecha_desde,
        "fecha_hasta": fecha_hasta,
        "responsabilidades": responsabilidades,
        "logros": logros,
        "estudios": main_education,
        "telefono": telefono,
        "email": email,
        "ciudad": ciudad,
        "linkedin": linkedin,
        "otras_redes": otras_redes,
        "all_jobs": all_jobs,
        "all_education": all_education,
        "skills": skills,
        "idiomas": idiomas,
        "certificaciones": certificaciones
    }

def extract_job_info(pdf_text):
    """
    Extraer información completa de experiencia laboral
    
    Returns:
        tuple: (diccionario con información del trabajo más reciente, lista con todos los trabajos)
    """
    # Patrones para identificar secciones de experiencia laboral
    patrones_experiencia = [
        r"EXPERIENCIA(?:\s+LABORAL|\s+PROFESIONAL)?",
        r"HISTORIAL(?:\s+LABORAL|\s+DE\s+TRABAJO)?",
        r"TRAYECTORIA(?:\s+LABORAL|\s+PROFESIONAL)?",
        r"EMPLEOS(?:\s+ANTERIORES)?"
    ]
    
    all_jobs = []
    job_section = extract_section(pdf_text, patrones_experiencia)
    
    if job_section:
        # Patrón para identificar trabajos individuales (cargo + empresa + fechas)
        jobs_pattern = r"([\w\s]+)\s+[-–]\s+([\w\s\.]+)\s+\((\w+\s+\d{4})\s*(?:[-–]\s*(\w+\s+\d{4}|Actual|Presente))?\)"
        jobs = re.findall(jobs_pattern, job_section, re.IGNORECASE)
        
        # Para cada trabajo encontrado, extraer información detallada
        for i, (cargo, empresa, fecha_desde, fecha_hasta) in enumerate(jobs):
            # Determinar dónde termina este trabajo (inicio del siguiente o fin de sección)
            job_start = job_section.find(f"{cargo} – {empresa}")
            next_job_start = len(job_section)
            
            if i < len(jobs) - 1:
                next_cargo, next_empresa = jobs[i+1][0], jobs[i+1][1]
                next_job_text = f"{next_cargo} – {next_empresa}"
                next_pos = job_section.find(next_job_text)
                if next_pos > -1:
                    next_job_start = next_pos
            
            # Extraer el texto completo de este trabajo
            job_text = job_section[job_start:next_job_start].strip()
            
            # Extraer responsabilidades y logros
            responsabilidades = extract_responsibilities(job_text)
            logros = extract_achievements(job_text)
            
            job_info = {
                "cargo": cargo.strip(),
                "empresa": empresa.strip(),
                "fecha_desde": fecha_desde.strip(),
                "fecha_hasta": fecha_hasta.strip() if fecha_hasta else "Actual",
                "responsabilidades": responsabilidades,
                "logros": logros,
                "texto_completo": job_text
            }
            
            all_jobs.append(job_info)
    
    # Devolver el trabajo más reciente (primero en la lista) y todos los trabajos
    return all_jobs[0] if all_jobs else {}, all_jobs

def extract_education(pdf_text):
    """
    Extraer información educativa completa
    
    Returns:
        tuple: (información del estudio principal, lista con todos los estudios)
    """
    # Patrones para identificar secciones de educación
    patrones_educacion = [
        r"EDUCACIÓN(?:\s+ACADÉMICA)?",
        r"FORMACIÓN(?:\s+ACADÉMICA)?",
        r"ESTUDIOS",
        r"HISTORIAL(?:\s+ACADÉMICO)"
    ]
    
    all_education = []
    education_section = extract_section(pdf_text, patrones_educacion)
    
    if education_section:
        # Patrón para identificar estudios individuales (título + institución + fechas)
        education_pattern = r"([\w\s]+)\s+[-–]\s+([\w\s\.]+)\s+\((\w+\s+\d{4})\s*(?:[-–]\s*(\w+\s+\d{4}|Actual|Presente))?\)"
        educations = re.findall(education_pattern, education_section, re.IGNORECASE)
        
        # Para cada estudio encontrado, extraer información detallada
        for i, (titulo, institucion, fecha_desde, fecha_hasta) in enumerate(educations):
            # Determinar dónde termina este estudio
            edu_start = education_section.find(f"{titulo} – {institucion}")
            next_edu_start = len(education_section)
            
            if i < len(educations) - 1:
                next_titulo, next_institucion = educations[i+1][0], educations[i+1][1]
                next_edu_text = f"{next_titulo} – {next_institucion}"
                next_pos = education_section.find(next_edu_text)
                if next_pos > -1:
                    next_edu_start = next_pos
            
            # Extraer el texto completo de este estudio
            edu_text = education_section[edu_start:next_edu_start].strip()
            
            # Extraer detalles adicionales como promedio, tesis, reconocimientos
            promedio = extract_grade_average(edu_text)
            tesis = extract_thesis(edu_text)
            reconocimientos = extract_academic_achievements(edu_text)
            
            education_info = {
                "titulo": titulo.strip(),
                "institucion": institucion.strip(),
                "fecha_desde": fecha_desde.strip(),
                "fecha_hasta": fecha_hasta.strip() if fecha_hasta else "Actual",
                "promedio": promedio,
                "tesis": tesis,
                "reconocimientos": reconocimientos,
                "texto_completo": edu_text
            }
            
            all_education.append(education_info)
    
    # Devolver el estudio principal (generalmente el más alto nivel) y todos los estudios
    main_education = ""
    if all_education:
        # Priorizar estudios superiores
        for edu in all_education:
            titulo = edu["titulo"].lower()
            if any(nivel in titulo for nivel in ["doctorado", "maestría", "máster", "posgrado"]):
                main_education = f"{edu['titulo']} - {edu['institucion']}"
                break
        
        if not main_education:
            # Si no hay estudios superiores, usar el primero
            main_education = f"{all_education[0]['titulo']} - {all_education[0]['institucion']}"
    
    return main_education, all_education

def extract_skills(pdf_text):
    """
    Extraer habilidades completas con nivel de competencia si está disponible
    
    Returns:
        list: Lista de diccionarios con habilidad y nivel
    """
    # Patrones para identificar secciones de habilidades
    patrones_habilidades = [
        r"HABILIDADES(?:\s+TÉCNICAS|\s+Y\s+COMPETENCIAS)?",
        r"COMPETENCIAS",
        r"CONOCIMIENTOS(?:\s+TÉCNICOS)?",
        r"DESTREZAS"
    ]
    
    skills = []
    skills_section = extract_section(pdf_text, patrones_habilidades)
    
    if skills_section:
        # Intentar extraer habilidades con nivel (ejemplo: "Python - Avanzado")
        skills_pattern = r"([\w\s\+\#\.]+)\s*[-–:]\s*(Básico|Intermedio|Avanzado|Experto|\d+%)"
        skills_with_level = re.findall(skills_pattern, skills_section, re.IGNORECASE)
        
        if skills_with_level:
            for skill, level in skills_with_level:
                skills.append({
                    "habilidad": skill.strip(),
                    "nivel": level.strip()
                })
        else:
            # Si no hay niveles, extraer lista simple de habilidades
            # Buscar listas con viñetas o separadas por comas
            bullet_pattern = r"[•\-\*]\s*([\w\s\+\#\.]+)"
            bullet_skills = re.findall(bullet_pattern, skills_section)
            
            if bullet_skills:
                for skill in bullet_skills:
                    skills.append({
                        "habilidad": skill.strip(),
                        "nivel": ""
                    })
            else:
                # Intentar separar por comas o puntos y comas
                comma_skills = re.split(r',|;', skills_section)
                for skill in comma_skills:
                    if skill.strip() and not any(patron in skill for patron in patrones_habilidades):
                        skills.append({
                            "habilidad": skill.strip(),
                            "nivel": ""
                        })
    
    return skills

def extract_contact_info(pdf_text):
    """
    Extraer información de contacto detallada
    
    Returns:
        tuple: (teléfono, email, ciudad, linkedin, otras_redes)
    """
    # Extraer teléfono
    telefono_pattern = r"(?:Tel[éeè]fono|Celular|Móvil|Contacto)?\s*[:\.]?\s*(\+?\d{1,4}[\s\-\.]?\d{1,3}[\s\-\.]?\d{3,4}[\s\-\.]?\d{2,4})"
    telefono_match = re.search(telefono_pattern, pdf_text, re.IGNORECASE)
    telefono = telefono_match.group(1).strip() if telefono_match else ""
    
    # Extraer email
    email_pattern = r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
    email_match = re.search(email_pattern, pdf_text)
    email = email_match.group(0).strip() if email_match else ""
    
    # Extraer ciudad
    ciudad_pattern = r"(?:Ciudad|Ubicación|Dirección|Residencia)?\s*[:\.]?\s*([\w\s]+(?:,\s*[\w\s]+)?)"
    ciudad_match = re.search(ciudad_pattern, pdf_text, re.IGNORECASE)
    ciudad = ciudad_match.group(1).strip() if ciudad_match else ""
    
    # Extraer LinkedIn
    linkedin_pattern = r"(?:LinkedIn|In)?\s*[:\.]?\s*((?:linkedin\.com/in/|www\.linkedin\.com/in/)[a-zA-Z0-9\-]+)"
    linkedin_match = re.search(linkedin_pattern, pdf_text, re.IGNORECASE)
    linkedin = linkedin_match.group(1).strip() if linkedin_match else ""
    
    # Extraer otras redes sociales
    otras_redes = {}
    # GitHub
    github_pattern = r"(?:GitHub|Git)?\s*[:\.]?\s*((?:github\.com/|www\.github\.com/)[a-zA-Z0-9\-]+)"
    github_match = re.search(github_pattern, pdf_text, re.IGNORECASE)
    if github_match:
        otras_redes["GitHub"] = github_match.group(1).strip()
    
    # Twitter/X
    twitter_pattern = r"(?:Twitter|X)?\s*[:\.]?\s*((?:twitter\.com/|x\.com/)[a-zA-Z0-9\-]+)"
    twitter_match = re.search(twitter_pattern, pdf_text, re.IGNORECASE)
    if twitter_match:
        otras_redes["Twitter"] = twitter_match.group(1).strip()
    
    return telefono, email, ciudad, linkedin, otras_redes

def extract_professional_profile(pdf_text):
    """
    Extraer perfil profesional completo
    
    Returns:
        str: Texto completo del perfil profesional
    """
    # Patrones para identificar secciones de perfil profesional
    patrones_perfil = [
        r"PERFIL(?:\s+PROFESIONAL)?",
        r"RESUMEN(?:\s+PROFESIONAL)?",
        r"ACERCA\s+DE\s+MÍ",
        r"SOBRE\s+MÍ",
        r"PRESENTACIÓN"
    ]
    
    perfil_section = extract_section(pdf_text, patrones_perfil)
    
    # Limpiar el perfil para eliminar el título de la sección
    if perfil_section:
        for patron in patrones_perfil:
            perfil_section = re.sub(f"{patron}[:\.\s]+", "", perfil_section, flags=re.IGNORECASE)
    
    return perfil_section.strip()

def extract_languages(pdf_text):
    """
    Extraer idiomas y nivel de competencia
    
    Returns:
        list: Lista de diccionarios con idioma y nivel
    """
    # Patrones para identificar secciones de idiomas
    patrones_idiomas = [
        r"IDIOMAS",
        r"LENGUAJES",
        r"COMPETENCIAS\s+LINGÜÍSTICAS"
    ]
    
    idiomas = []
    idiomas_section = extract_section(pdf_text, patrones_idiomas)
    
    if idiomas_section:
        # Intentar extraer idiomas con nivel
        idiomas_pattern = r"([\w\s]+)\s*[-–:]\s*(Nativo|Básico|Intermedio|Avanzado|Fluido|B1|B2|C1|C2|A1|A2|\d+%)"
        idiomas_with_level = re.findall(idiomas_pattern, idiomas_section, re.IGNORECASE)
        
        if idiomas_with_level:
            for idioma, nivel in idiomas_with_level:
                idiomas.append({
                    "idioma": idioma.strip(),
                    "nivel": nivel.strip()
                })
        else:
            # Si no hay niveles, extraer lista simple de idiomas
            bullet_pattern = r"[•\-\*]\s*([\w\s]+)"
            bullet_idiomas = re.findall(bullet_pattern, idiomas_section)
            
            if bullet_idiomas:
                for idioma in bullet_idiomas:
                    idiomas.append({
                        "idioma": idioma.strip(),
                        "nivel": ""
                    })
    
    return idiomas

def extract_certifications(pdf_text):
    """
    Extraer certificaciones con detalles
    
    Returns:
        list: Lista de diccionarios con certificación, entidad y fecha
    """
    # Patrones para identificar secciones de certificaciones
    patrones_certificaciones = [
        r"CERTIFICACIONES",
        r"CERTIFICADOS",
        r"CURSOS",
        r"FORMACIÓN\s+COMPLEMENTARIA"
    ]
    
    certificaciones = []
    cert_section = extract_section(pdf_text, patrones_certificaciones)
    
    if cert_section:
        # Intentar extraer certificaciones con entidad y fecha
        cert_pattern = r"([\w\s]+)\s*[-–]\s*([\w\s\.]+)\s*(?:\((\w+\s+\d{4})\))?"
        certs = re.findall(cert_pattern, cert_section, re.IGNORECASE)
        
        if certs:
            for cert, entidad, fecha in certs:
                certificaciones.append({
                    "certificacion": cert.strip(),
                    "entidad": entidad.strip(),
                    "fecha": fecha.strip()
                })
        else:
            # Si no hay formato estándar, extraer lista simple
            bullet_pattern = r"[•\-\*]\s*([\w\s,\.]+)"
            bullet_certs = re.findall(bullet_pattern, cert_section)
            
            if bullet_certs:
                for cert in bullet_certs:
                    certificaciones.append({
                        "certificacion": cert.strip(),
                        "entidad": "",
                        "fecha": ""
                    })
    
    return certificaciones

def extract_section(pdf_text, patrones):
    """
    Extraer una sección completa del texto usando patrones específicos
    
    Args:
        pdf_text (str): Texto completo del PDF
        patrones (list): Lista de patrones regex para identificar el inicio de la sección
    
    Returns:
        str: Texto completo de la sección
    """
    section_text = ""
    
    # Encontrar todas las posibles secciones del CV
    all_sections_pattern = r"([A-ZÁÉÍÓÚÑ\s]+)(?::|\.|\n)"
    all_sections = re.findall(all_sections_pattern, pdf_text)
    
    # Buscar la sección específica
    section_start = -1
    section_name = ""
    
    for patron in patrones:
        for match in re.finditer(patron, pdf_text, re.IGNORECASE):
            if match.start() > section_start:
                section_start = match.start()
                section_name = match.group(0)
    
    if section_start >= 0:
        # Encontrar el inicio de la siguiente sección
        section_end = len(pdf_text)
        
        for section in all_sections:
            if not any(re.search(patron, section, re.IGNORECASE) for patron in patrones):
                section_match = re.search(f"{re.escape(section)}(?::|\.|\n)", pdf_text[section_start:])
                if section_match:
                    next_section_start = section_start + section_match.start()
                    if next_section_start > section_start and next_section_start < section_end:
                        section_end = next_section_start
        
        # Extraer el texto de la sección
        section_text = pdf_text[section_start:section_end].strip()
        
        # Eliminar el título de la sección
        section_text = re.sub(f"{re.escape(section_name)}[:\.\s]+", "", section_text, count=1, flags=re.IGNORECASE)
    
    return section_text

# Funciones auxiliares para extraer información específica

def extract_identification(pdf_text):
    """Extraer número de identificación"""
    id_patterns = [
        r"(?:C\.?C\.?|Cédula|Documento|ID)[\s:\.]*(\d[\d\.\s]+\d)",
        r"(?:Identificación|DNI)[\s:\.]*(\d[\d\.\s]+\d)"
    ]
    
    for pattern in id_patterns:
        match = re.search(pattern, pdf_text, re.IGNORECASE)
        if match:
            return match.group(1).strip().replace(" ", "").replace(".", "")
    
    return ""

def extract_name(pdf_text):
    """Extraer nombre completo"""
    # Buscar en las primeras líneas del documento (generalmente el nombre está al principio)
    first_lines = pdf_text.split('\n')[:5]
    first_text = ' '.join(first_lines)
    
    # Patrones para nombres
    name_patterns = [
        r"(?:Nombre|Nombres y Apellidos)[\s:\.]+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){1,3})",
        r"^([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){1,3})"
    ]
    
    for pattern in name_patterns:
        match = re.search(pattern, first_text)
        if match:
            return match.group(1).strip()
    
    # Si no se encuentra con patrones específicos, tomar la primera línea que parece un nombre
    for line in first_lines:
        line = line.strip()
        # Un nombre típico tiene al menos dos palabras, todas empiezan con mayúscula
        words = line.split()
        if len(words) >= 2 and all(word[0].isupper() for word in words if word):
            return line
    
    return ""

def extract_age(pdf_text):
    """Extraer edad"""
    age_patterns = [
        r"(?:Edad|Age)[\s:\.]+(\d{1,2})",
        r"(\d{1,2})\s+(?:años|years)",
        r"Fecha de Nacimiento[\s:\.]+(\d{1,2}/\d{1,2}/\d{4}|\d{1,2}\s+de\s+\w+\s+de\s+\d{4})"
    ]
    
    for pattern in age_patterns:
        match = re.search(pattern, pdf_text, re.IGNORECASE)
        if match:
            # Si es fecha de nacimiento, calcular edad aproximada
            birth_date = match.group(1)
            if '/' in birth_date or 'de' in birth_date:
                return "Calculada de fecha de nacimiento"
            return match.group(1)
    
    return ""

def extract_experience(pdf_text):
    """Extraer años de experiencia"""
    exp_patterns = [
        r"(\d+)[\s\+]+(?:años|years)(?:\s+de\s+experiencia)?",
        r"Experiencia(?:\s+de|\s+laboral)?[\s:\.]+(\d+)[\s\+]+(?:años|years)"
    ]
    
    for pattern in exp_patterns:
        match = re.search(pattern, pdf_text, re.IGNORECASE)
        if match:
            return match.group(1)
    
    # Si no hay mención explícita, intentar calcularlo de las fechas de trabajo
    job_info, all_jobs = extract_job_info(pdf_text)
    if all_jobs:
        # Tomar el trabajo más antiguo y calcular diferencia aproximada
        oldest_job_start = all_jobs[-1].get("fecha_desde", "")
        if oldest_job_start and "20" in oldest_job_start:  # Validación simple
            start_year_match = re.search(r"(\d{4})", oldest_job_start)
            if start_year_match:
                start_year = int(start_year_match.group(1))
                current_year = 2025  # Actualizar según corresponda
                experience_years = current_year - start_year
                return str(experience_years)
    
    return ""

def extract_responsibilities(job_text):
    """Extraer responsabilidades del texto de un trabajo"""
    resp_patterns = [
        r"(?:Responsabilidades|Funciones|Tareas)[\s:\.]+(.+?)(?=Logros|Resultados|\Z)",
        r"(?:•|\*|-)\s*(.+)"
    ]
    
    for pattern in resp_patterns:
        matches = re.findall(pattern, job_text, re.IGNORECASE | re.DOTALL)
        if matches:
            responsibilities = []
            for match in matches:
                # Limpiar y dividir por viñetas si hay múltiples
                items = re.split(r"(?:•|\*|-)\s*", match)
                responsibilities.extend([item.strip() for item in items if item.strip()])
            return responsibilities
    
    return []

def extract_achievements(job_text):
    """Extraer logros del texto de un trabajo"""
    achieve_patterns = [
        r"(?:Logros|Resultados|Éxitos|Achievements)[\s:\.]+(.+?)(?=\Z)",
        r"(?:•|\*|-)\s*(.+)"
    ]
    
    for pattern in achieve_patterns:
        matches = re.findall(pattern, job_text, re.IGNORECASE | re.DOTALL)
        if matches:
            achievements = []
            for match in matches:
                # Limpiar y dividir por viñetas si hay múltiples
                items = re.split(r"(?:•|\*|-)\s*", match)
                achievements.extend([item.strip() for item in items if item.strip()])
            return achievements
    
    return []

def extract_grade_average(edu_text):
    """Extraer promedio académico del texto de un estudio"""
    grade_patterns = [
        r"(?:Promedio|GPA|Calificación)[\s:\.]+(\d+(?:\.\d+)?)",
        r"(\d+(?:\.\d+)?)/(?:4\.0|5\.0|10)"
    ]
    
    for pattern in grade_patterns:
        match = re.search(pattern, edu_text, re.IGNORECASE)
        if match:
            return match.group(1)
    
    return ""

def extract_thesis(edu_text):
    """Extraer información de tesis del texto de un estudio"""
    thesis_pattern = r"(?:Tesis|Proyecto|Trabajo\s+Final)[\s:\.]+(.+?)(?=\n\n|\Z)"
    match = re.search(thesis_pattern, edu_text, re.IGNORECASE | re.DOTALL)
    
    if match:
        return match.group(1).strip()
    
    return ""

def extract_academic_achievements(edu_text):
    """Extraer reconocimientos académicos del texto de un estudio"""
    achieve_pattern = r"(?:Reconocimientos|Distinciones|Honores|Méritos)[\s:\.]+(.+?)(?=\n\n|\Z)"
    match = re.search(achieve_pattern, edu_text, re.IGNORECASE | re.DOTALL)
    
    if match:
        return match.group(1).strip()
    
    return ""

def upload_tab():
    """Pestaña para subir archivo y extraer datos"""
    st.header("Cargar Hoja de Vida")
    st.write("Cargue un archivo PDF de hoja de vida para extraer la información.")
    
    # Cargar credenciales
    creds, config = load_credentials_from_toml()
    if not creds:
        st.error("No se pudieron cargar las credenciales. Verifique el archivo secrets.toml")
        return None, None
    
    # Conectar a Google Sheets
    client = get_google_sheets_connection(creds)
    if not client:
        st.error("No se pudo establecer conexión con Google Sheets")
        return None, None
    
    # Subir archivo PDF
    uploaded_file = st.file_uploader("Selecciona un archivo PDF de hoja de vida", type="pdf")
    
    if uploaded_file is not None:
        # Extraer texto del PDF
        pdf_text = extract_text_from_pdf(uploaded_file)
        
        if pdf_text:
            with st.expander("Ver texto extraído del PDF"):
                st.text(pdf_text[:1000] + "..." if len(pdf_text) > 1000 else pdf_text)
                print(f'Texto Extraido {pdf_text}')
            
            # Extraer todos los datos
            cv_data = extract_resume_data(pdf_text)
            
            # Mostrar información extraída
            st.subheader("Información extraída")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"**Identificación:** {cv_data['identificacion']}")
                st.write(f"**Nombres:** {cv_data['nombres']}")
                st.write(f"**Edad:** {cv_data['edad']}")
                st.write(f"**Experiencia:** {cv_data['experiencia']} años")
                st.write(f"**Cargo:** {cv_data['cargo']}")
                st.write(f"**Empresa:** {cv_data['empresa']}")

                # Mostrar perfil profesional completo con expansor
                with st.expander("**Perfil Profesional**"):
                    st.write(cv_data['perfil_profesional'])
                
                # Mostrar experiencia laboral detallada
                with st.expander("**Experiencia Laboral Detallada**"):
                    for job in cv_data['all_jobs']:
                        st.markdown(f"### {job['cargo']} - {job['empresa']}")
                        st.write(f"*{job['fecha_desde']} - {job['fecha_hasta']}*")
                        
                        if job['responsabilidades']:
                            st.write("**Responsabilidades:**")
                            for resp in job['responsabilidades']:
                                st.write(f"• {resp}")
                        
                        if job['logros']:
                            st.write("**Logros:**")
                            for logro in job['logros']:
                                st.write(f"• {logro}")
                        
                        st.write("---")
            
            with col2:
                st.write(f"**Fecha Desde:** {cv_data['fecha_desde']}")
                st.write(f"**Fecha Hasta:** {cv_data['fecha_hasta']}")
                st.write(f"**Estudios:** {cv_data['estudios']}")
                st.write(f"**Teléfono:** {cv_data['telefono']}")
                st.write(f"**Email:** {cv_data['email']}")
                st.write(f"**Ciudad Actual:** {cv_data['ciudad']}")
                
                # Mostrar LinkedIn y otras redes
                if 'linkedin' in cv_data and cv_data['linkedin']:
                    st.write(f"**LinkedIn:** {cv_data['linkedin']}")
                
                if 'otras_redes' in cv_data and cv_data['otras_redes']:
                    for red, url in cv_data['otras_redes'].items():
                        st.write(f"**{red}:** {url}")
                
                # Mostrar habilidades con niveles
                with st.expander("**Habilidades y Competencias**"):
                    for skill in cv_data['skills']:
                        if skill['nivel']:
                            st.write(f"• {skill['habilidad']} - {skill['nivel']}")
                        else:
                            st.write(f"• {skill['habilidad']}")
                
                # Mostrar idiomas
                if 'idiomas' in cv_data and cv_data['idiomas']:
                    with st.expander("**Idiomas**"):
                        for idioma in cv_data['idiomas']:
                            if idioma['nivel']:
                                st.write(f"• {idioma['idioma']} - {idioma['nivel']}")
                            else:
                                st.write(f"• {idioma['idioma']}")
                
                # Mostrar certificaciones
                if 'certificaciones' in cv_data and cv_data['certificaciones']:
                    with st.expander("**Certificaciones**"):
                        for cert in cv_data['certificaciones']:
                            cert_text = f"• {cert['certificacion']}"
                            if cert['entidad']:
                                cert_text += f" - {cert['entidad']}"
                            if cert['fecha']:
                                cert_text += f" ({cert['fecha']})"
                            st.write(cert_text)
            
            # Mostrar educación detallada
            with st.expander("**Educación Detallada**"):
                for edu in cv_data['all_education']:
                    st.markdown(f"### {edu['titulo']} - {edu['institucion']}")
                    st.write(f"*{edu['fecha_desde']} - {edu['fecha_hasta']}*")
                    
                    if edu['promedio']:
                        st.write(f"**Promedio:** {edu['promedio']}")
                    
                    if edu['tesis']:
                        st.write(f"**Tesis:** {edu['tesis']}")
                    
                    if edu['reconocimientos']:
                        st.write(f"**Reconocimientos:** {edu['reconocimientos']}")
                    
                    st.write("---")
            
            # Permitir editar la información
            st.subheader("Editar información")
            
            col1, col2 = st.columns(2)
            
            with col1:
                identificacion = st.text_input("Identificación", value=cv_data['identificacion'])
                nombres = st.text_input("Nombres", value=cv_data['nombres'])
                edad = st.text_input("Edad", value=cv_data['edad'])
                experiencia = st.text_input("Experiencia (años)", value=cv_data['experiencia'])
                cargo = st.text_input("Cargo", value=cv_data['cargo'])
                empresa = st.text_input("Empresa", value=cv_data['empresa'])
                perfil = st.text_area("Perfil Profesional", value=cv_data['perfil_profesional'])
            
            with col2:
                fecha_desde = st.text_input("Fecha Desde", value=cv_data['fecha_desde'])
                fecha_hasta = st.text_input("Fecha Hasta", value=cv_data['fecha_hasta'])
                estudios = st.text_input("Estudios", value=cv_data['estudios'])
                telefono = st.text_input("Teléfono", value=cv_data['telefono'])
                email = st.text_input("Email", value=cv_data['email'])
                ciudad = st.text_input("Ciudad Actual", value=cv_data['ciudad'])
                
                # Agregar campos para LinkedIn y otras redes
                linkedin = ""
                if 'linkedin' in cv_data:
                    linkedin = st.text_input("LinkedIn", value=cv_data['linkedin'])
            
            # Pestaña para editar habilidades
            st.subheader("Editar Habilidades")
            skills_container = st.container()
            with skills_container:
                skills_list = []
                
                # Mostrar habilidades existentes con opción de editar
                for i, skill in enumerate(cv_data['skills']):
                    col1, col2, col3 = st.columns([3, 2, 1])
                    with col1:
                        skill_name = st.text_input(f"Habilidad {i+1}", value=skill['habilidad'])
                    with col2:
                        skill_level = st.text_input(f"Nivel {i+1}", value=skill['nivel'])
                    with col3:
                        if st.button(f"Eliminar {i+1}"):
                            pass  # En una implementación real, esto eliminaría la habilidad
                    
                    skills_list.append({"habilidad": skill_name, "nivel": skill_level})
                
                # Opción para agregar nueva habilidad
                if st.button("Agregar Habilidad"):
                    skills_list.append({"habilidad": "", "nivel": ""})
            
            # Pestaña para editar experiencia laboral
            st.subheader("Editar Experiencia Laboral")
            jobs_container = st.container()
            with jobs_container:
                jobs_list = []
                
                # Mostrar trabajos existentes con opción de editar
                for i, job in enumerate(cv_data['all_jobs']):
                    with st.expander(f"Trabajo {i+1}: {job['cargo']} - {job['empresa']}"):
                        cargo_job = st.text_input(f"Cargo {i+1}", value=job['cargo'])
                        empresa_job = st.text_input(f"Empresa {i+1}", value=job['empresa'])
                        fecha_desde_job = st.text_input(f"Fecha Desde {i+1}", value=job['fecha_desde'])
                        fecha_hasta_job = st.text_input(f"Fecha Hasta {i+1}", value=job['fecha_hasta'])
                        
                        # Responsabilidades como lista editable
                        st.write("**Responsabilidades:**")
                        responsabilidades = []
                        for j, resp in enumerate(job['responsabilidades']):
                            resp_text = st.text_area(f"Responsabilidad {i+1}.{j+1}", value=resp)
                            responsabilidades.append(resp_text)
                        
                        # Logros como lista editable
                        st.write("**Logros:**")
                        logros = []
                        for j, logro in enumerate(job['logros']):
                            logro_text = st.text_area(f"Logro {i+1}.{j+1}", value=logro)
                            logros.append(logro_text)
                        
                        # Opción para eliminar este trabajo
                        if st.button(f"Eliminar Trabajo {i+1}"):
                            pass  # En una implementación real, esto eliminaría el trabajo
                    
                    jobs_list.append({
                        "cargo": cargo_job,
                        "empresa": empresa_job,
                        "fecha_desde": fecha_desde_job,
                        "fecha_hasta": fecha_hasta_job,
                        "responsabilidades": responsabilidades,
                        "logros": logros
                    })
                
                # Opción para agregar nuevo trabajo
                if st.button("Agregar Trabajo"):
                    jobs_list.append({
                        "cargo": "",
                        "empresa": "",
                        "fecha_desde": "",
                        "fecha_hasta": "",
                        "responsabilidades": [],
                        "logros": []
                    })
            
            # Pestaña para editar educación
            st.subheader("Editar Educación")
            education_container = st.container()
            with education_container:
                education_list = []
                
                # Mostrar estudios existentes con opción de editar
                for i, edu in enumerate(cv_data['all_education']):
                    with st.expander(f"Estudio {i+1}: {edu['titulo']} - {edu['institucion']}"):
                        titulo_edu = st.text_input(f"Título {i+1}", value=edu['titulo'])
                        institucion_edu = st.text_input(f"Institución {i+1}", value=edu['institucion'])
                        fecha_desde_edu = st.text_input(f"Fecha Desde Edu {i+1}", value=edu['fecha_desde'])
                        fecha_hasta_edu = st.text_input(f"Fecha Hasta Edu {i+1}", value=edu['fecha_hasta'])
                        promedio_edu = st.text_input(f"Promedio {i+1}", value=edu['promedio'])
                        tesis_edu = st.text_area(f"Tesis {i+1}", value=edu['tesis'])
                        reconocimientos_edu = st.text_area(f"Reconocimientos {i+1}", value=edu['reconocimientos'])
                        
                        # Opción para eliminar este estudio
                        if st.button(f"Eliminar Estudio {i+1}"):
                            pass  # En una implementación real, esto eliminaría el estudio
                    
                    education_list.append({
                        "titulo": titulo_edu,
                        "institucion": institucion_edu,
                        "fecha_desde": fecha_desde_edu,
                        "fecha_hasta": fecha_hasta_edu,
                        "promedio": promedio_edu,
                        "tesis": tesis_edu,
                        "reconocimientos": reconocimientos_edu
                    })
                
                # Opción para agregar nuevo estudio
                if st.button("Agregar Estudio"):
                    education_list.append({
                        "titulo": "",
                        "institucion": "",
                        "fecha_desde": "",
                        "fecha_hasta": "",
                        "promedio": "",
                        "tesis": "",
                        "reconocimientos": ""
                    })
            
            # Datos a guardar (versión ampliada)
            data = {
                "Identificacion": identificacion,
                "Nombres": nombres,
                "Edad": edad,
                "Experiencia": experiencia,
                "Cargo": cargo,
                "Empresa": empresa,
                "Fecha Desde": fecha_desde,
                "Fecha Hasta": fecha_hasta,
                "Estudios": estudios,
                "Telefono": telefono,
                "Email": email,
                "Ciudad Actual": ciudad,
                "LinkedIn": linkedin,
                "Perfil Profesional": perfil,
                "Habilidades": json.dumps(skills_list),
                "Trabajos": json.dumps(jobs_list),
                "Educacion": json.dumps(education_list),
                "Idiomas": json.dumps(cv_data.get('idiomas', [])),
                "Certificaciones": json.dumps(cv_data.get('certificaciones', []))
            }
            
            # Botón para guardar
            if st.button("Guardar en Google Sheets"):
                success, message = save_to_google_sheet(client, data)
                if success:
                    st.success(message)
                else:
                    st.error(message)
            
            return client, cv_data
        else:
            st.error("No se pudo extraer texto del PDF. Verifique que el archivo sea válido.")
    
    return client, None
   # Función mejorada para evaluar trabajos con las fechas más recientes
   def get_date_score(job):
            """
            Calcula una puntuación basada en las fechas del trabajo.
            Prioriza trabajos actuales y luego ordena jerárquicamente por:
            1. Trabajos actuales (hasta "presente" o equivalente)
            2. Año de finalización (mayor primero)
            3. Mes de finalización (mayor primero)
            4. Día de finalización (mayor primero)
            
            Para fechas en formato extenso como "01 de octubre de 2018":
            - Se procesa completamente el año, mes y día
            - Se da peso extra a este formato por su precisión
            """
            # Primero evaluamos si es trabajo actual (hasta "presente")
            is_current = False
            if job["fecha_hasta"]:
                is_current = job["fecha_hasta"].lower() in ['presente', 'actual', 'actualidad', 'present', 'current']
    
            # Si es trabajo actual, tiene máxima prioridad
            if is_current:
                return float('inf')  # Infinito para asegurar que siempre esté primero
    
            # Inicializar los valores de año, mes y día para fecha_hasta
            end_year = 0
            end_month = 0
            end_day = 0
    
            # Inicializar los valores de año, mes y día para fecha_desde
            start_year = 0
            start_month = 0
            start_day = 0
    
            # Procesamiento de fecha_hasta (prioridad alta)
            # Comprobar primero si tenemos un objeto datetime
            if job["end_date"]:
                # Extraer año, mes y día del objeto datetime
                end_year = job["end_date"].year
                end_month = job["end_date"].month
                end_day = job["end_date"].day
            else:
                # Si no hay end_date pero hay fecha_hasta (como texto)
                if job["fecha_hasta"]:
                    # Verificar si es formato extendido "DD de Mes de YYYY"
                    extended_match = re.search(r'(\d{1,2})\s+de\s+([a-zé]{3,12})\s+de\s+(\d{4})', job["fecha_hasta"], re.IGNORECASE)
                    if extended_match:
                        end_day = int(extended_match.group(1))
                        month_text = extended_match.group(2).lower()
                        end_year = int(extended_match.group(3))
                        
                        month_map = {
                            'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 
                            'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8, 
                            'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
                        }
                        
                        if month_text in month_map:
                            end_month = month_map[month_text]
                    else:
                        # Verificar formato "DD Mes YYYY"
                        extended_match2 = re.search(r'(\d{1,2})\s+([a-zé]{3,12})\s+(\d{4})', job["fecha_hasta"], re.IGNORECASE)
                        if extended_match2:
                            end_day = int(extended_match2.group(1))
                            month_text = extended_match2.group(2).lower()
                            end_year = int(extended_match2.group(3))
                            
                            month_map = {
                                'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 
                                'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8, 
                                'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
                            }
                            
                            if month_text in month_map:
                                end_month = month_map[month_text]
                        else:
                            # Extraer año
                            year_match = re.search(r'(\d{4})', job["fecha_hasta"])
                            if year_match:
                                end_year = int(year_match.group(1))
                        
                            # Extraer mes
                            month_map = {
                                'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 
                                'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8, 
                                'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
                            }
                        
                            for month_name, month_value in month_map.items():
                                if month_name in job["fecha_hasta"].lower():
                                    end_month = month_value
                                    break
                            
                            # Extraer día
                            day_match = re.search(r'\b(\d{1,2})\b', job["fecha_hasta"])
                            if day_match:
                                end_day = int(day_match.group(1))
            
            # Procesamiento de fecha_desde (menor prioridad)
            if job["start_date"]:
                # Extraer año, mes y día del objeto datetime
                start_year = job["start_date"].year
                start_month = job["start_date"].month
                start_day = job["start_date"].day
            else:
                # Si no hay start_date pero hay fecha_desde (como texto)
                if job["fecha_desde"]:
                    # Verificar si es formato extendido "DD de Mes de YYYY"
                    extended_match = re.search(r'(\d{1,2})\s+de\s+([a-zé]{3,12})\s+de\s+(\d{4})', job["fecha_desde"], re.IGNORECASE)
                    if extended_match:
                        start_day = int(extended_match.group(1))
                        month_text = extended_match.group(2).lower()
                        start_year = int(extended_match.group(3))
                        
                        month_map = {
                            'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 
                            'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8, 
                            'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
                        }
                        
                        if month_text in month_map:
                            start_month = month_map[month_text]
                    else:
                        # Verificar formato "DD Mes YYYY"
                        extended_match2 = re.search(r'(\d{1,2})\s+([a-zé]{3,12})\s+(\d{4})', job["fecha_desde"], re.IGNORECASE)
                        if extended_match2:
                            start_day = int(extended_match2.group(1))
                            month_text = extended_match2.group(2).lower()
                            start_year = int(extended_match2.group(3))
                            
                            month_map = {
                                'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 
                                'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8, 
                                'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
                            }
                            
                            if month_text in month_map:
                                start_month = month_map[month_text]
                        else:
                            # Extraer año
                            year_match = re.search(r'(\d{4})', job["fecha_desde"])
                            if year_match:
                                start_year = int(year_match.group(1))
                        
                            # Extraer mes
                            month_map = {
                                'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 
                                'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8, 
                                'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
                            }
                        
                            for month_name, month_value in month_map.items():
                                if month_name in job["fecha_desde"].lower():
                                    start_month = month_value
                                    break
                            
                            # Extraer día
                            day_match = re.search(r'\b(\d{1,2})\b', job["fecha_desde"])
                            if day_match:
                                start_day = int(day_match.group(1))
                
            # Calcular puntuación final
            # Priorizamos principalmente por fecha_hasta (fecha de finalización)
            # Usamos una fórmula para asignar más peso al año, seguido del mes y luego el día
            score = end_year * 10000 + end_month * 100 + end_day
            
            # Si la fecha de finalización es igual entre dos trabajos, desempatamos con fecha_desde
            # Damos preferencia a trabajos que empezaron antes (más experiencia en el mismo periodo)
            if score == 0 or (start_year > 0 and end_year == 0):
                # Si no hay fecha_hasta pero sí hay fecha_desde, usamos ésta como referencia
                score = start_year * 10000 + start_month * 100 + start_day
                
            return score

def summary_tab(cv_data):
    """Pestaña para mostrar un resumen de la hoja de vida"""
    st.header("Resumen de Hoja de Vida")
    
    if not cv_data:
        st.warning("No hay datos para mostrar. Por favor cargue un archivo PDF en la pestaña 'Cargar CV'.")
        return
    
    # Información personal
    st.subheader("Información Personal")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Nombre:** {cv_data['nombres']}")
        st.markdown(f"**Identificación:** {cv_data['identificacion']}")
        st.markdown(f"**Edad:** {cv_data['edad']} años")
    with col2:
        st.markdown(f"**Email:** {cv_data['email']}")
        st.markdown(f"**Teléfono:** {cv_data['telefono']}")
        st.markdown(f"**Ciudad:** {cv_data['ciudad']}")
    
    # Resumen profesional
    st.subheader("Resumen Profesional")
    if cv_data['experiencia']:
        st.markdown(f"Profesional con **{cv_data['experiencia']} años** de experiencia.")
    else:
        st.markdown("Profesional con experiencia en el sector.")
    
    if cv_data['cargo'] and cv_data['empresa']:
        st.markdown(f"Actualmente o recientemente se desempeña como **{cv_data['cargo']}** en **{cv_data['empresa']}**.")
    
    # Experiencia laboral
    st.subheader("Experiencia Laboral")
    if cv_data['all_jobs'] and len(cv_data['all_jobs']) > 0:
        for i, job in enumerate(cv_data['all_jobs'][:1]):  # Mostrar hasta 3 trabajos
            with st.container():
                st.markdown(f"**{job['cargo']}**")
                st.markdown(f"*{job['empresa']}*")
                if job['fecha_desde'] or job['fecha_hasta']:
                    st.markdown(f"_{job['fecha_desde']} - {job['fecha_hasta']}_")
                st.markdown("---")
    else:
        st.write("No se encontró información detallada sobre experiencia laboral.")
    
    # Educación
    st.subheader("Formación Académica")
    if cv_data['all_education'] and len(cv_data['all_education']) > 0:
        for edu in cv_data['all_education'][:3]:  # Mostrar hasta 3 titulaciones
            st.markdown(f"• {edu}")
    else:
        st.write("No se encontró información detallada sobre formación académica.")
    
    # Habilidades
    st.subheader("Habilidades y Competencias")
    if cv_data['skills'] and len(cv_data['skills']) > 0:
        skills_cols = st.columns(2)
        half = len(cv_data['skills']) // 2 + len(cv_data['skills']) % 2
        with skills_cols[0]:
            for skill in cv_data['skills'][:half]:
                st.markdown(f"• {skill}")
        with skills_cols[1]:
            for skill in cv_data['skills'][half:]:
                st.markdown(f"• {skill}")
    else:
        st.write("No se encontró información detallada sobre habilidades.")
    
    # Gráfico simple que muestra la experiencia laboral
    if cv_data['all_jobs'] and len(cv_data['all_jobs']) > 0:
        st.subheader("Línea de Tiempo Profesional")
        try:
            import plotly.graph_objects as go
            
            # Preparar datos para la línea de tiempo
            jobs_for_chart = []
            
            for job in cv_data['all_jobs']:
                if job['fecha_desde'] and job['empresa']:
                    # Simplificar las fechas para el gráfico
                    fecha_desde = job['fecha_desde'].split('/')[-1] if '/' in job['fecha_desde'] else job['fecha_desde']
                    fecha_hasta = job['fecha_hasta'].split('/')[-1] if '/' in job['fecha_hasta'] else job['fecha_hasta']
                    if fecha_hasta.lower() in ['presente', 'actual', 'present', 'current']:
                        fecha_hasta = '2025'
                    
                    # Asegurarse de que son números
                    try:
                        fecha_desde = int(re.search(r'\d{4}', fecha_desde).group(0))
                        if re.search(r'\d{4}', fecha_hasta):
                            fecha_hasta = int(re.search(r'\d{4}', fecha_hasta).group(0))
                        else:
                            continue
                        
                        jobs_for_chart.append({
                            'empresa': job['empresa'],
                            'cargo': job['cargo'],
                            'inicio': fecha_desde,
                            'fin': fecha_hasta
                        })
                    except:
                        continue
            
                jobs_for_chart.sort(key=lambda x: x['inicio'])
                
                # Crear el gráfico de línea de tiempo
                fig = go.Figure()
                
                # Añadir cada trabajo como una barra en la línea de tiempo
                for job in jobs_for_chart:
                    duration = job['fin'] - job['inicio']
                    fig.add_trace(go.Bar(
                        x=[duration],
                        y=[job['empresa']],
                        orientation='h',
                        base=[job['inicio']],
                        width=0.5,
                        text=f"{job['cargo']} ({job['inicio']}-{job['fin']})",
                        hoverinfo="text",
                        marker=dict(color="rgba(0, 128, 255, 0.8)")
                    ))
                
                # Configurar layout
                fig.update_layout(
                    title="Experiencia Laboral por Años",
                    xaxis_title="Año",
                    yaxis_title="Empresa",
                    height=400,
                    showlegend=False
                )
                
                st.plotly_chart(fig, use_container_width=True)
            
        except Exception as e:
            st.warning(f"No se pudo generar el gráfico de línea de tiempo: {str(e)}")

