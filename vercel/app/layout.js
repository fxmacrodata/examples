export const metadata = {
  title: 'FX Market Intelligence – FXMacroData',
  description:
    'Interactive FX market intelligence dashboard: precious metals prices, COT positioning, and economic release calendar — powered by the FXMacroData API.',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
