import type { Metadata } from "next"
import Link from "next/link"
import { WaitlistForm } from "@/components/waitlist-form"

export const metadata: Metadata = {
  title: "CF0 - Spreadsheet with LLM",
  description: "A powerful spreadsheet application with built-in LLM capabilities",
}

export default function LandingPage() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-50 w-full border-b bg-white">
        <div className="container flex h-14 items-center">
          <div className="mr-4 flex">
            <Link href="/" className="mr-6 flex items-center space-x-2">
              <span className="font-bold">CF0</span>
            </Link>
          </div>
          <div className="flex flex-1 items-center justify-end space-x-4">
            <nav className="flex items-center space-x-2">
              <Link href="/login" className="px-4 py-2 text-sm font-medium text-gray-700 hover:text-gray-900">
                Sign In
              </Link>
            </nav>
          </div>
        </div>
      </header>
      <main className="flex-1">
        <section className="w-full py-12 md:py-24 lg:py-32">
          <div className="container px-4 md:px-6">
            <div className="grid gap-6 lg:grid-cols-2 lg:gap-12">
              <div className="flex flex-col justify-center space-y-4">
                <div className="space-y-2">
                  <h1 className="text-3xl font-bold tracking-tighter sm:text-4xl md:text-5xl">
                    Spreadsheets Powered by AI
                  </h1>
                  <p className="max-w-[600px] text-gray-500 md:text-xl/relaxed lg:text-base/relaxed xl:text-xl/relaxed">
                    CF0 combines the power of spreadsheets with AI to help you analyze and manipulate your data more
                    efficiently.
                  </p>
                </div>
                <div className="flex flex-col gap-2 min-[400px]:flex-row">
                  <WaitlistForm />
                </div>
              </div>
              <div className="flex items-center justify-center">
                <div className="relative h-[350px] w-full overflow-hidden rounded-xl border bg-gray-100 p-2">
                  <div className="h-full w-full bg-white rounded-lg border border-gray-200 shadow-sm">
                    <div className="flex h-8 items-center border-b bg-gray-50 px-4">
                      <div className="flex space-x-1">
                        <div className="h-2 w-2 rounded-full bg-gray-300" />
                        <div className="h-2 w-2 rounded-full bg-gray-300" />
                        <div className="h-2 w-2 rounded-full bg-gray-300" />
                      </div>
                      <div className="ml-2 text-xs font-medium">Spreadsheet</div>
                    </div>
                    <div className="grid grid-cols-5 border-b">
                      <div className="border-r p-2 text-center text-xs font-medium text-gray-500"></div>
                      <div className="border-r p-2 text-center text-xs font-medium text-gray-500">A</div>
                      <div className="border-r p-2 text-center text-xs font-medium text-gray-500">B</div>
                      <div className="border-r p-2 text-center text-xs font-medium text-gray-500">C</div>
                      <div className="p-2 text-center text-xs font-medium text-gray-500">D</div>
                    </div>
                    <div className="grid grid-cols-5 border-b">
                      <div className="border-r p-2 text-center text-xs font-medium text-gray-500">1</div>
                      <div className="border-r p-2 text-xs">Revenue</div>
                      <div className="border-r p-2 text-xs">$10,000</div>
                      <div className="border-r p-2 text-xs"></div>
                      <div className="p-2 text-xs"></div>
                    </div>
                    <div className="grid grid-cols-5 border-b">
                      <div className="border-r p-2 text-center text-xs font-medium text-gray-500">2</div>
                      <div className="border-r p-2 text-xs">Expenses</div>
                      <div className="border-r p-2 text-xs">$5,000</div>
                      <div className="border-r p-2 text-xs"></div>
                      <div className="p-2 text-xs"></div>
                    </div>
                    <div className="grid grid-cols-5 border-b">
                      <div className="border-r p-2 text-center text-xs font-medium text-gray-500">3</div>
                      <div className="border-r p-2 text-xs">Profit</div>
                      <div className="border-r p-2 text-xs">$5,000</div>
                      <div className="border-r p-2 text-xs"></div>
                      <div className="p-2 text-xs"></div>
                    </div>
                    <div className="absolute bottom-4 right-4 flex items-center space-x-2 rounded-lg bg-blue-500 px-3 py-2 text-white shadow-lg">
                      <span className="text-xs font-medium">Ask AI</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>
        <section className="w-full py-12 md:py-24 lg:py-32 bg-gray-100">
          <div className="container px-4 md:px-6">
            <div className="flex flex-col items-center justify-center space-y-4 text-center">
              <div className="space-y-2">
                <h2 className="text-3xl font-bold tracking-tighter sm:text-4xl md:text-5xl">Features</h2>
                <p className="max-w-[900px] text-gray-500 md:text-xl/relaxed lg:text-base/relaxed xl:text-xl/relaxed">
                  CF0 combines the power of spreadsheets with AI to help you analyze and manipulate your data more
                  efficiently.
                </p>
              </div>
            </div>
            <div className="mx-auto grid max-w-5xl grid-cols-1 gap-6 py-12 md:grid-cols-3">
              <div className="flex flex-col items-center space-y-2 rounded-lg border bg-white p-6 shadow-sm">
                <div className="rounded-full bg-gray-100 p-3">
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    width="24"
                    height="24"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    className="h-6 w-6"
                  >
                    <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
                    <polyline points="14 2 14 8 20 8" />
                    <path d="M8 13h2" />
                    <path d="M8 17h2" />
                    <path d="M14 13h2" />
                    <path d="M14 17h2" />
                  </svg>
                </div>
                <h3 className="text-lg font-bold">Spreadsheet</h3>
                <p className="text-center text-sm text-gray-500">
                  Familiar spreadsheet interface with formulas, formatting, and more.
                </p>
              </div>
              <div className="flex flex-col items-center space-y-2 rounded-lg border bg-white p-6 shadow-sm">
                <div className="rounded-full bg-gray-100 p-3">
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    width="24"
                    height="24"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    className="h-6 w-6"
                  >
                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                  </svg>
                </div>
                <h3 className="text-lg font-bold">AI Assistant</h3>
                <p className="text-center text-sm text-gray-500">
                  Ask questions about your data and get instant insights.
                </p>
              </div>
              <div className="flex flex-col items-center space-y-2 rounded-lg border bg-white p-6 shadow-sm">
                <div className="rounded-full bg-gray-100 p-3">
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    width="24"
                    height="24"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    className="h-6 w-6"
                  >
                    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10" />
                  </svg>
                </div>
                <h3 className="text-lg font-bold">Data Security</h3>
                <p className="text-center text-sm text-gray-500">
                  Your data is encrypted and secure. We never share your data with third parties.
                </p>
              </div>
            </div>
          </div>
        </section>
      </main>
      <footer className="flex flex-col gap-2 sm:flex-row py-6 w-full border-t items-center px-4 md:px-6">
        <p className="text-xs text-gray-500">© 2023 CF0. All rights reserved.</p>
        <nav className="sm:ml-auto flex gap-4 sm:gap-6">
          <Link className="text-xs hover:underline underline-offset-4" href="#">
            Terms of Service
          </Link>
          <Link className="text-xs hover:underline underline-offset-4" href="#">
            Privacy
          </Link>
        </nav>
      </footer>
    </div>
  )
}
