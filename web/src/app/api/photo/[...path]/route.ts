import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";

async function proxy(req: NextRequest, path: string[]) {
  const base = (process.env.PHOTO_API_URL || "http://127.0.0.1:8222").replace(/\/$/, "");
  const token = process.env.PHOTO_API_TOKEN || "";
  const target = `${base}/v1/${path.join("/")}${req.nextUrl.search}`;

  const headers = new Headers();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const init: RequestInit = { method: req.method, headers };
  if (req.method !== "GET" && req.method !== "HEAD") {
    const contentType = req.headers.get("content-type") || "";
    if (contentType.includes("multipart/form-data")) {
      init.body = await req.formData();
    } else {
      const buf = await req.arrayBuffer();
      if (buf.byteLength) init.body = buf;
      if (contentType) headers.set("Content-Type", contentType);
    }
  }

  const upstream = await fetch(target, init);
  const body = await upstream.arrayBuffer();
  const out = new NextResponse(body, { status: upstream.status });
  const pass = upstream.headers.get("content-type");
  if (pass) out.headers.set("content-type", pass);
  return out;
}

type Ctx = { params: Promise<{ path: string[] }> };

export async function GET(req: NextRequest, ctx: Ctx) {
  return proxy(req, (await ctx.params).path);
}
export async function POST(req: NextRequest, ctx: Ctx) {
  return proxy(req, (await ctx.params).path);
}
export async function PUT(req: NextRequest, ctx: Ctx) {
  return proxy(req, (await ctx.params).path);
}
