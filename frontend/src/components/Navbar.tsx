import { NavLink } from "react-router-dom";

export default function Navbar() {
  return (
    <nav
      style={{
        display: "flex",
        alignItems: "center",
        padding: "0 24px",
        height: "60px",
        background: "#111",
        borderBottom: "1px solid #222",
        flexShrink: 0,
      }}
    >
      {/* Logo / Brand */}
      <div
        style={{
          fontSize: "20px",
          fontWeight: 700,
          color: "#fff",
          marginRight: "40px",
        }}
      >
        Flyer Builder
      </div>

      {/* Navigation Links */}
      <div style={{ display: "flex", gap: "8px" }}>
        <NavLink
          to="/"
          end
          style={({ isActive }) => ({
            padding: "8px 16px",
            borderRadius: "6px",
            color: isActive ? "#fff" : "#888",
            background: isActive ? "#2a2a2a" : "transparent",
            textDecoration: "none",
            fontSize: "14px",
            fontWeight: 500,
            transition: "all 0.2s",
          })}
        >
          Create Flyer
        </NavLink>

        <NavLink
          to="/edit-template"
          style={({ isActive }) => ({
            padding: "8px 16px",
            borderRadius: "6px",
            color: isActive ? "#fff" : "#888",
            background: isActive ? "#2a2a2a" : "transparent",
            textDecoration: "none",
            fontSize: "14px",
            fontWeight: 500,
            transition: "all 0.2s",
          })}
        >
          Edit Template
        </NavLink>
      </div>
    </nav>
  );
}