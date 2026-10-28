type PageHeaderProps = {
  title: string
  description: string
}

export function PageHeader({ title, description }: PageHeaderProps) {
  return (
    <header>
      <h1 className="text-title">{title}</h1>
      <p className="mt-1 text-muted">{description}</p>
    </header>
  )
}
