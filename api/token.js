module.exports = (req, res) => {
  const token = process.env.WAVE_API_TOKEN || "";
  res.setHeader("Content-Type", "application/json");
  res.statusCode = 200;
  res.end(JSON.stringify({ token }));
};
