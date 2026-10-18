import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import DocumentIntelligenceWorkspace from '../DocumentIntelligenceWorkspace';
import App from '../../App';
import * as api from '../../services/api';

// Mock Leaflet
vi.mock('leaflet', () => ({
  default: {
    map: () => ({
      setView: vi.fn(),
      getZoom: () => 14,
      remove: vi.fn(),
      invalidateSize: vi.fn(),
      on: vi.fn(),
      fitBounds: vi.fn(),
    }),
    tileLayer: () => ({ addTo: () => {} }),
    layerGroup: () => ({ addTo: function() { return this; }, clearLayers: function() { return this; } }),
    geoJSON: () => ({ addTo: () => {} }),
    polygon: () => ({ addTo: () => {} }),
    circle: () => ({ addTo: () => {} }),
    marker: () => ({
      addTo: function() { return this; },
      bindPopup: function() { return this; },
      setLatLng: vi.fn(),
      getLatLng: () => ({ lat: 28.5921, lng: 77.0460 }),
      on: vi.fn(),
    }),
    divIcon: () => ({}),
  },
}));

describe('DocumentIntelligenceWorkspace Component', () => {
  const mockAnalysisResponse = {
    documents: [
      {
        document_id: 'doc-1',
        filename: 'Sale_Deed_Defence_Colony.txt',
        file_size_bytes: 1420,
        page_count: 2,
        document_type: 'Sale Deed',
        document_type_confidence: 0.95,
        is_scanned_or_empty: false,
        warnings: [],
        parties: [
          {
            name: 'Rajesh Kumar Sharma',
            role: 'Vendor / Seller / First Party',
            details: 'First party / transferor',
            status: 'explicitly_stated',
            evidence: {
              page_number: 1,
              excerpt_text: 'BETWEEN Shri Rajesh Kumar Sharma hereinafter called the VENDOR',
              confidence: 0.95,
              line_number: 5,
            },
          },
          {
            name: 'Priya Anand Verma',
            role: 'Purchaser / Buyer / Second Party',
            details: 'Second party / transferee',
            status: 'explicitly_stated',
            evidence: {
              page_number: 1,
              excerpt_text: 'AND Smt. Priya Anand Verma hereinafter called the PURCHASER',
              confidence: 0.95,
              line_number: 9,
            },
          },
        ],
        property_details: {
          address: 'Block-C, Defence Colony, New Delhi',
          plot_survey_number: 'Plot No. 104',
          area_sqft: '250 sq yards',
          boundaries: {
            North: 'Road 30ft wide',
            South: 'Plot No. 105',
          },
          status: 'explicitly_stated',
          evidence: {
            page_number: 1,
            excerpt_text: 'Plot No. 104, Block-C, Defence Colony, New Delhi',
            confidence: 0.9,
            line_number: 12,
          },
        },
        financials: {
          declared_consideration: '₹ 4,50,00,000',
          numeric_amount: 45000000.0,
          currency: 'INR',
          stamp_duty: '₹ 27,00,000',
          registration_fee: '₹ 4,50,000',
          status: 'explicitly_stated',
          evidence: {
            page_number: 2,
            excerpt_text: 'sum of Rs. 4,50,00,000/- fully received by the Vendor',
            confidence: 0.9,
            line_number: 18,
          },
        },
        dates: {
          execution_date: '12th day of June, 2024',
          registration_date: '14th day of June, 2024',
          status: 'explicitly_stated',
        },
        registration: {
          sub_registrar_office: 'SRO-VII, Defence Colony, New Delhi',
          registration_number: 'DL-SR7-2024-8841',
          book_number: '1',
          status: 'explicitly_stated',
          evidence: {
            page_number: 2,
            excerpt_text: 'Sub-Registrar Office: SRO-VII, Defence Colony, New Delhi',
            confidence: 0.9,
            line_number: 22,
          },
        },
        raw_text_length: 1200,
        analyzed_at: '2024-06-14T10:00:00Z',
      },
      {
        document_id: 'doc-2',
        filename: 'Draft_Agreement.txt',
        file_size_bytes: 980,
        page_count: 1,
        document_type: 'Agreement to Sell',
        document_type_confidence: 0.92,
        is_scanned_or_empty: false,
        warnings: [],
        parties: [
          {
            name: 'Rajesh Kumar Sharma',
            role: 'Vendor / Seller',
            status: 'explicitly_stated',
          },
        ],
        property_details: {
          address: 'Defence Colony, New Delhi',
          plot_survey_number: 'Plot No. 104-A',
          status: 'explicitly_stated',
        },
        financials: {
          declared_consideration: '₹ 4,80,00,000',
          numeric_amount: 48000000.0,
          status: 'explicitly_stated',
        },
        dates: {},
        registration: {},
        raw_text_length: 800,
        analyzed_at: '2024-06-14T10:00:00Z',
      },
    ],
    comparison: {
      document_count: 2,
      compared_documents: ['Sale_Deed_Defence_Colony.txt', 'Draft_Agreement.txt'],
      summary: 'Detected 2 high-severity discrepancies between instruments.',
      overall_risk_level: 'high',
      matches: ['Party Rajesh Kumar Sharma present in both instruments'],
      discrepancies: [
        {
          field_name: 'Declared Consideration Amount',
          severity: 'high',
          status: 'mismatch',
          description: 'Consideration amounts conflict between instruments: ₹ 4,50,00,000 vs ₹ 4,80,00,000.',
          document_values: {
            'Sale_Deed_Defence_Colony.txt': '₹ 4,50,00,000',
            'Draft_Agreement.txt': '₹ 4,80,00,000',
          },
          recommendation: 'Reconcile earnest advance deposit receipts vs final sale consideration terms.',
        },
        {
          field_name: 'Property Identification',
          severity: 'high',
          status: 'mismatch',
          description: 'Plot numbers differ: Plot No. 104 vs Plot No. 104-A.',
          document_values: {
            'Sale_Deed_Defence_Colony.txt': 'Plot No. 104',
            'Draft_Agreement.txt': 'Plot No. 104-A',
          },
          recommendation: 'Verify exact site layout and mutation extract to confirm plot designation.',
        },
      ],
    },
    legal_disclaimer: 'NIVAS Document Intelligence provides automated informational text analysis and cross-referencing for decision support only. It does NOT constitute a legal title opinion.',
    registry_verification_status: 'not_verified_live_registry_unavailable',
  };

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders hero banner, title, decision-support disclaimer and offline status', () => {
    render(<DocumentIntelligenceWorkspace />);
    expect(screen.getByText(/Document Intelligence & Legal Extraction/i)).toBeDefined();
    expect(screen.getByText(/Decision Support Only/i)).toBeDefined();
    expect(screen.getByText(/Sub-Registrar DB:/i)).toBeDefined();
  });

  it('loads sample documents when sample bundle button is clicked', async () => {
    vi.spyOn(api, 'fetchSampleDocuments').mockResolvedValue({
      samples: [
        { filename: 'Sample_Agreement.txt', content: 'Agreement content' },
        { filename: 'Sample_Sale_Deed.txt', content: 'Sale Deed content' },
      ],
    });

    render(<DocumentIntelligenceWorkspace />);
    const loadBtn = screen.getByRole('button', { name: /Load Pre-Baked Delhi Sample Bundle/i });
    fireEvent.click(loadBtn);

    await waitFor(() => {
      expect(api.fetchSampleDocuments).toHaveBeenCalled();
      expect(screen.getByText('Sample_Agreement.txt')).toBeDefined();
      expect(screen.getByText('Sample_Sale_Deed.txt')).toBeDefined();
    });
  });

  it('analyzes documents and displays extraction cards and cross-document comparison', async () => {
    vi.spyOn(api, 'fetchSampleDocuments').mockResolvedValue({
      samples: [
        { filename: 'Sample_Agreement.txt', content: 'Agreement' },
        { filename: 'Sample_Sale_Deed.txt', content: 'Sale Deed' },
      ],
    });
    vi.spyOn(api, 'analyzeDocuments').mockResolvedValue(mockAnalysisResponse);

    render(<DocumentIntelligenceWorkspace />);

    // Load samples
    const loadBtn = screen.getByRole('button', { name: /Load Pre-Baked Delhi Sample Bundle/i });
    fireEvent.click(loadBtn);

    await waitFor(() => {
      expect(screen.getByText('Sample_Agreement.txt')).toBeDefined();
    });

    // Click Analyze
    const analyzeBtn = screen.getByRole('button', { name: /Analyze & Cross-Verify Documents/i });
    fireEvent.click(analyzeBtn);

    await waitFor(() => {
      expect(api.analyzeDocuments).toHaveBeenCalled();
      expect(screen.getByText(/Cross-Document Reconciliation Matrix/i)).toBeDefined();
      expect(screen.getByText(/HIGH Risk Discrepancies/i)).toBeDefined();
      expect(screen.getByText(/Declared Consideration Amount/i)).toBeDefined();
      expect(screen.getAllByText(/Rajesh Kumar Sharma/i).length).toBeGreaterThan(0);
      expect(screen.getByText(/Priya Anand Verma/i)).toBeDefined();
      expect(screen.getAllByText(/4,50,00,000/).length).toBeGreaterThan(0);
    });
  });

  it('opens evidence popover with exact citation when Page badge is clicked', async () => {
    vi.spyOn(api, 'fetchSampleDocuments').mockResolvedValue({
      samples: [
        { filename: 'Sample_Agreement.txt', content: 'Agreement' },
        { filename: 'Sample_Sale_Deed.txt', content: 'Sale Deed' },
      ],
    });
    vi.spyOn(api, 'analyzeDocuments').mockResolvedValue(mockAnalysisResponse);

    render(<DocumentIntelligenceWorkspace />);
    fireEvent.click(screen.getByRole('button', { name: /Load Pre-Baked Delhi Sample Bundle/i }));
    await waitFor(() => expect(screen.getByText('Sample_Agreement.txt')).toBeDefined());

    fireEvent.click(screen.getByRole('button', { name: /Analyze & Cross-Verify Documents/i }));
    await waitFor(() => expect(screen.getAllByText(/Rajesh Kumar Sharma/i).length).toBeGreaterThan(0));

    // Click Page 1 badge for Rajesh Kumar Sharma
    const pageBadges = screen.getAllByRole('button', { name: /Page 1/i });
    expect(pageBadges.length).toBeGreaterThan(0);
    fireEvent.click(pageBadges[0]);

    // Modal should show excerpt
    await waitFor(() => {
      expect(screen.getByText(/BETWEEN Shri Rajesh Kumar Sharma hereinafter called the VENDOR/i)).toBeDefined();
    });
  });

  it('navigates to Document Intelligence via App.jsx header switcher', async () => {
    render(<App />);

    const docIntelTabBtn = screen.getByRole('button', { name: /Document Intelligence/i });
    expect(docIntelTabBtn).toBeDefined();

    fireEvent.click(docIntelTabBtn);

    await waitFor(() => {
      expect(screen.getByText(/Document Intelligence & Legal Extraction/i)).toBeDefined();
    });
  });
});
