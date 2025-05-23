import Image from "next/image"
import { Star } from "lucide-react"

export function TestimonialsSection() {
  return (
    <section className="w-full py-12 md:py-24 lg:py-32 bg-background">
      <div className="container px-4 md:px-6">
        <div className="flex flex-col items-center justify-center space-y-4 text-center">
          <div className="space-y-2">
            <div className="inline-block rounded-lg bg-primary/10 px-3 py-1 text-sm text-primary">Testimonials</div>
            <h2 className="text-3xl font-bold tracking-tighter sm:text-5xl">
              The Choice of SaaS Founders, The Trust of Brands
            </h2>
            <p className="max-w-[900px] text-muted-foreground md:text-xl/relaxed lg:text-base/relaxed xl:text-xl/relaxed">
              Don't take our word for it. See what our customers have to say about GridFlow.
            </p>
          </div>
        </div>
        <div className="mx-auto grid max-w-5xl gap-6 py-12 lg:grid-cols-3">
          {[
            {
              name: "Alex Chen",
              role: "Product Manager",
              company: "TechCorp",
              image: "/placeholder.svg?height=100&width=100",
              quote:
                "GridFlow has transformed how our team collaborates. We've seen a 30% increase in productivity since implementing it.",
            },
            {
              name: "Sarah Johnson",
              role: "CTO",
              company: "StartupX",
              image: "/placeholder.svg?height=100&width=100",
              quote:
                "The intuitive interface and powerful features make GridFlow the perfect solution for our growing team.",
            },
            {
              name: "Michael Brown",
              role: "Marketing Director",
              company: "GrowthLabs",
              image: "/placeholder.svg?height=100&width=100",
              quote:
                "I can't imagine running our marketing campaigns without GridFlow. It's become an essential part of our workflow.",
            },
          ].map((testimonial) => (
            <div
              key={testimonial.name}
              className="flex flex-col justify-between rounded-lg border bg-background p-6 shadow-sm"
            >
              <div className="space-y-4">
                <div className="flex">
                  {Array(5)
                    .fill(null)
                    .map((_, i) => (
                      <Star key={i} className="h-5 w-5 fill-primary text-primary" />
                    ))}
                </div>
                <p className="text-muted-foreground">"{testimonial.quote}"</p>
              </div>
              <div className="mt-6 flex items-center space-x-4">
                <Image
                  src={testimonial.image || "/placeholder.svg"}
                  alt={testimonial.name}
                  width={40}
                  height={40}
                  className="rounded-full"
                />
                <div>
                  <p className="text-sm font-medium">{testimonial.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {testimonial.role}, {testimonial.company}
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
