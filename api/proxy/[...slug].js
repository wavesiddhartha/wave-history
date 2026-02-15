const getRawBody = (req) =>
  new Promise((resolve, reject) => {
    const chunks = [];
    req.on("data", (c) => chunks.push(c));
    req.on("end", () => resolve(Buffer.concat(chunks)));
    req.on("error", reject);
  });

module.exports = async (req, res) => {
  const backend = process.env.BACKEND_URL;
  if (!backend) {
    res.setHeader("Content-Type", "application/json");
    res.statusCode = 500;
    res.end(JSON.stringify({ error: "BACKEND_URL not configured" }));
    return;
  }

  const slug = req.query.slug;
  const path = Array.isArray(slug) ? slug.join("/") : slug || "";
  const url = `${backend.replace(/\/$/, "")}/api/${path}`;

  const raw = await getRawBody(req);

  const headers = { ...req.headers };
  delete headers.host;

  const init = {
    method: req.method,
    headers,
    body: raw && raw.length ? raw : undefined,
    redirect: "manual",
  };

  try {
    const backendRes = await fetch(url, init);
    // copy headers
    backendRes.headers.forEach((v, k) => res.setHeader(k, v));
    res.statusCode = backendRes.status;
    const buf = Buffer.from(await backendRes.arrayBuffer());
    res.end(buf);
  } catch (err) {
    res.setHeader("Content-Type", "application/json");
    res.statusCode = 502;
    res.end(JSON.stringify({ error: "Bad Gateway", detail: String(err) }));
  }
};
