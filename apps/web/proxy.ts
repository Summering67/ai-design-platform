import { NextResponse } from "next/server"
import type { NextRequest } from "next/server"

export const proxy = (request: NextRequest) => {
  if (request.cookies.has("aidp_session")) return NextResponse.next()
  const login = new URL("/login", request.url)
  login.searchParams.set("next", `${request.nextUrl.pathname}${request.nextUrl.search}`)
  return NextResponse.redirect(login)
}

export const config = { matcher: ["/workspace/:path*"] }
