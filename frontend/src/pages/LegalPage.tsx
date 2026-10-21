const pages = {
  privacidade: {
    title: 'Política de privacidade',
    sections: [
      [
        'Quem trata os dados',
        'O Ponto é operado pela pessoa ou organização que disponibilizou esta instância. Não há, nesta fase, uma empresa comercial registada no produto: o responsável pelo tratamento é quem corre o servidor a que estás ligado.',
      ],
      [
        'Que dados guardamos',
        'Da conta Google: identificador, email, nome e fotografia. Do teu uso: o CV (ficheiro e texto extraído), a lista de empresas e contactos, emails encontrados em páginas públicas, o estado das candidaturas e, se ligares o Gmail, tokens de acesso cifrados. Guardamos também a data de cada análise, rascunho, procura de email e envio, para aplicar os limites de uso. Não guardamos a palavra-passe da Google.',
      ],
      [
        'Para que servem',
        'Para te autenticar, procurar vagas alinhadas com o CV, guardar a lista de prospeção, redigir rascunhos e, só depois da tua confirmação, enviar emails em teu nome e seguir respostas.',
      ],
      [
        'Com quem partilhamos',
        'Com a Google, no login e no envio de email. Com o fornecedor de IA (Mistral AI, servidores na UE), que recebe o texto do CV e os dados da vaga para ler o perfil e redigir os emails. Com sites de empresas e portais de emprego, quando o Ponto consulta páginas públicas para listar vagas ou encontrar um contacto. Não vendemos dados nem os usamos para publicidade.',
      ],
      [
        'Quanto tempo ficam',
        'Enquanto a conta existir. Podes exportar uma cópia em JSON e apagar a conta: isso remove o perfil, o CV, a lista, as sessões e os tokens Gmail desta instância.',
      ],
      [
        'Os teus direitos',
        'Aceder, exportar e apagar os dados. O pedido de apagar conta está na app, no painel da conta. Para questões, usa o email da conta Google com que entraste.',
      ],
      [
        'Cookies',
        'Usamos um cookie de sessão httpOnly (ponto_session) para te manter ligado. Não usamos cookies de rastreio.',
      ],
    ],
  },
  termos: {
    title: 'Termos de utilização',
    sections: [
      [
        'O que é o Ponto',
        'Uma ferramenta de apoio à procura de emprego: analisa o CV, sugere vagas, ajuda a encontrar contactos e prepara emails. Não garante entrevistas, respostas nem contratação.',
      ],
      [
        'A tua responsabilidade',
        'Confirmas cada email antes de enviar. Usas o serviço de forma pessoal, sem disparos em massa nem dados de outras pessoas sem autorização. O conteúdo que envias é da tua responsabilidade.',
      ],
      [
        'Fontes de terceiros',
        'As vagas e os sites das empresas pertencem a terceiros. O Ponto não controla essa informação e pode estar desatualizada ou incompleta.',
      ],
      [
        'Inteligência artificial',
        'A leitura do CV e a redação dos emails são feitas por um modelo de IA da Mistral AI. O resultado é uma sugestão e pode ter erros: revê sempre antes de enviar.',
      ],
      [
        'Conta',
        'O acesso faz-se com Google. Podes terminar sessão, exportar os dados ou apagar a conta. Quem opera a instância pode recusar contas que abusem do serviço.',
      ],
      [
        'Alterações',
        'Se os termos ou a privacidade mudarem de forma relevante, pedimos de novo o teu aceite no login.',
      ],
    ],
  },
} as const

export type LegalSlug = keyof typeof pages

export function LegalPage({ kind }: { kind: LegalSlug }) {
  const page = pages[kind]

  return (
    <main className="legal-screen">
      <article className="legal-card">
        <a href="#vagas">Voltar</a>
        <h1>{page.title}</h1>
        {page.sections.map(([heading, text]) => (
          <section key={heading}>
            <h2>{heading}</h2>
            <p>{text}</p>
          </section>
        ))}
      </article>
    </main>
  )
}
