import Image from "next/image"
import Link from "next/link"

interface LogoProps {
  className?: string
  size?: "sm" | "md" | "lg"
  clickable?: boolean
}

export function Logo({ className, size = "md", clickable = true }: LogoProps) {
  const sizes = {
    sm: "text-lg",
    md: "text-xl",
    lg: "text-2xl",
  }

  const logoSizes = {
    sm: { width: 24, height: 24 },
    md: { width: 32, height: 32 },
    lg: { width: 40, height: 40 },
  }

  const logoContent = (
    <>
      <Image
        src="/logo.png"
        alt="cf0 Logo"
        width={logoSizes[size].width}
        height={logoSizes[size].height}
        className="object-contain"
        priority={size === "lg"}
      />
      <span className={`font-bold text-white ${sizes[size]}`}>
        cf
        <span className="relative inline-block">
          0
          <span className="absolute inset-0 flex items-center justify-center">
            <span className="h-[2px] w-[140%] bg-white -rotate-15 transform-gpu"></span>
          </span>
        </span>
      </span>
    </>
  )

  if (clickable) {
    return (
      <Link
        href="/"
        className={`flex items-center gap-2 hover:opacity-80 transition-opacity cursor-pointer ${className}`}
      >
        {logoContent}
      </Link>
    )
  }

  return <div className={`flex items-center gap-2 ${className}`}>{logoContent}</div>
}
