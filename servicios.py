import streamlit as st

class SocialMediaConsultant:
    def __init__(self):
        self.social_media = {
            "Facebook": {"url": "https://web.facebook.com/?_rdc=1&_rdr", "icon": "📘"},
            "Equis": {"url": "https://x.com/xmetaofficial", "icon": "X"},
            "Instagram": {"url": "https://www.instagram.com/", "icon": "📷"},
            "LinkedIn": {"url": "https://co.linkedin.com/", "icon": "💼"},
            "YouTube": {"url": "https://www.youtube.com/?app=desktop&hl=es", "icon": "▶️"}
        }

    class Model:
        pageTitle = "***Consulta tus Redes Sociales***"

    def view(self, model):
        st.title(model.pageTitle)

    def render_ui(self):
        self.view(self.Model())

        st.write("Selecciona una red social para visitarla:")

        cols = st.columns(len(self.social_media))
        for i, (name, info) in enumerate(self.social_media.items()):
            with cols[i]:
                st.link_button(f"{info['icon']} {name}", info['url'])

        st.write("\n")
        st.write("O busca directamente en una red social:")
        search_term = st.text_input("Término de búsqueda")
        selected_social = st.selectbox("Selecciona la red social", 
                                       [f"{info['icon']} {name}" for name, info in self.social_media.items()])

        if st.button("Buscar"):
            platform = selected_social.split(' ', 1)[1]
            self.search_social_media(platform, search_term)

    def search_social_media(self, platform, term):
        search_urls = {
            "Facebook": f"https://web.facebook.com/search/top?q={term}",
            "Equis": f"https://x.com/search?q={term}",
            "Instagram": f"https://www.instagram.com/explore/tags/{term}/",
            "LinkedIn": f"https://www.linkedin.com/search/results/all/?keywords={term}",
            "YouTube": f"https://www.youtube.com/results?search_query={term}"
        }
        if platform in search_urls:
            st.link_button(f"Buscar '{term}' en {platform}", search_urls[platform])
        else:
            st.error(f"No se encontró la plataforma: {platform}")

#def main():
#    consultant = SocialMediaConsultant()
#    consultant.render_ui()

#if __name__ == "__main__":
#    main()
