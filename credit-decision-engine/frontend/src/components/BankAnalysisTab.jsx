import React from 'react';
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell
} from 'recharts';
import { AlertTriangle, CheckCircle, ArrowUpRight, ArrowDownLeft, Landmark } from 'lucide-react';

const BankAnalysisTab = ({ bankData }) => {
  if (!bankData) return (
    <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-secondary)' }}>
      No bank statement data available for this company.
    </div>
  );

  const { transactions, counterparty_risk, debt_service_ratio } = bankData;

  const COLORS = ['#3b82f6', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444'];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Top Metrics: DSR and Counterparty Risk */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
        {/* DSR Card */}
        <div style={{
          background: 'var(--card-bg)',
          backdropFilter: 'var(--glass-blur)',
          borderRadius: '20px',
          padding: '24px',
          border: '1px solid var(--border-color)',
          boxShadow: 'var(--card-shadow)'
        }}>
          <h3 style={{ fontSize: '18px', fontWeight: 'bold', color: 'var(--text-primary)', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Landmark size={20} color="#3b82f6" /> Debt Service Ratio (DSR)
          </h3>
          <div style={{ display: 'flex', alignItems: 'center', gap: '24px' }}>
            <div style={{
              width: '100px',
              height: '100px',
              borderRadius: '50%',
              border: `8px solid ${debt_service_ratio.status === 'Healthy' ? '#10b981' : debt_service_ratio.status === 'Warning' ? '#f59e0b' : '#ef4444'}`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '24px',
              fontWeight: 'bold',
              color: 'var(--text-primary)'
            }}>
              {Math.round(debt_service_ratio.value * 100)}%
            </div>
            <div>
              <p style={{ margin: '0 0 4px 0', fontSize: '14px', color: 'var(--text-secondary)' }}>Status: 
                <span style={{ fontWeight: 'bold', color: debt_service_ratio.status === 'Healthy' ? '#10b981' : '#ef4444', marginLeft: '4px' }}>
                  {debt_service_ratio.status}
                </span>
              </p>
              <p style={{ margin: 0, fontSize: '14px', color: 'var(--text-secondary)' }}>
                Avg Monthly Inflow: <span style={{ color: 'var(--text-primary)', fontWeight: '600' }}>₹{debt_service_ratio.monthly_average_inflow.toLocaleString()}</span>
              </p>
              <p style={{ margin: 0, fontSize: '14px', color: 'var(--text-secondary)' }}>
                Debt Obligations: <span style={{ color: 'var(--text-primary)', fontWeight: '600' }}>₹{debt_service_ratio.monthly_debt_obligations.toLocaleString()}</span>
              </p>
            </div>
          </div>
        </div>

        {/* Counterparty Risk Card */}
        <div style={{
          background: 'var(--card-bg)',
          backdropFilter: 'var(--glass-blur)',
          borderRadius: '20px',
          padding: '24px',
          border: '1px solid var(--border-color)',
          boxShadow: 'var(--card-shadow)'
        }}>
          <h3 style={{ fontSize: '18px', fontWeight: 'bold', color: 'var(--text-primary)', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <AlertTriangle size={20} color={counterparty_risk.risk_level === 'High' ? '#ef4444' : '#f59e0b'} /> Counterparty Risk
          </h3>
          <p style={{ margin: '0 0 12px 0', fontSize: '14px', color: 'var(--text-secondary)' }}>
            {counterparty_risk.description}
          </p>
          <div style={{ height: '120px' }}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={counterparty_risk.top_counterparties.map(([name, val]) => ({ name, value: val }))}
                  innerRadius={30}
                  outerRadius={50}
                  paddingAngle={5}
                  dataKey="value"
                >
                  {counterparty_risk.top_counterparties.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ backgroundColor: 'var(--card-bg)', borderColor: 'var(--border-color)', color: 'var(--text-primary)' }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Transaction Table */}
      <div style={{
        background: 'var(--card-bg)',
        backdropFilter: 'var(--glass-blur)',
        borderRadius: '20px',
        padding: '24px',
        border: '1px solid var(--border-color)',
        boxShadow: 'var(--card-shadow)'
      }}>
        <h3 style={{ fontSize: '18px', fontWeight: 'bold', color: 'var(--text-primary)', marginBottom: '20px' }}>
          📑 Recent Transactions
        </h3>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border-color)' }}>
                <th style={{ padding: '12px', color: 'var(--text-secondary)', fontWeight: '600', fontSize: '14px' }}>Date</th>
                <th style={{ padding: '12px', color: 'var(--text-secondary)', fontWeight: '600', fontSize: '14px' }}>Description</th>
                <th style={{ padding: '12px', color: 'var(--text-secondary)', fontWeight: '600', fontSize: '14px' }}>Type</th>
                <th style={{ padding: '12px', color: 'var(--text-secondary)', fontWeight: '600', fontSize: '14px', textAlign: 'right' }}>Amount</th>
              </tr>
            </thead>
            <tbody>
              {transactions.map((t, i) => (
                <tr key={i} style={{ borderBottom: '1px solid var(--border-color)', transition: 'background 0.2s' }}>
                  <td style={{ padding: '12px', color: 'var(--text-primary)', fontSize: '14px' }}>{t.date}</td>
                  <td style={{ padding: '12px', color: 'var(--text-primary)', fontSize: '14px' }}>{t.description}</td>
                  <td style={{ padding: '12px', fontSize: '14px' }}>
                    <span style={{ 
                      display: 'inline-flex', 
                      alignItems: 'center', 
                      gap: '4px',
                      padding: '4px 8px',
                      borderRadius: '12px',
                      background: t.type === 'credit' ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)',
                      color: t.type === 'credit' ? '#10b981' : '#ef4444',
                      fontWeight: '600',
                      fontSize: '12px'
                    }}>
                      {t.type === 'credit' ? <ArrowDownLeft size={14} /> : <ArrowUpRight size={14} />}
                      {t.type.toUpperCase()}
                    </span>
                  </td>
                  <td style={{ padding: '12px', color: 'var(--text-primary)', fontSize: '14px', fontWeight: 'bold', textAlign: 'right' }}>
                    ₹{t.amount.toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default BankAnalysisTab;
