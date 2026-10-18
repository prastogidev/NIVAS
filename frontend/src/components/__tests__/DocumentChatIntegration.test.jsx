import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import LivabilityWorkspace from '../LivabilityWorkspace';
import DocumentIntelligenceWorkspace from '../DocumentIntelligenceWorkspace';
import * as api from '../../services/api';

// Mock Leaflet
vi.mock('leaflet', () => {
  const mockMap = {
    setView: vi.fn(),
    getZoom: () => 14,
    remove: vi.fn(),
    invalidateSize: vi.fn(),
    on: vi.fn(),
  };

  return {
    default: {
      map: () => mockMap,
      tileLayer: () => ({ addTo: () => {} }),
      marker: () => ({
        addTo: function() { return this; },
        setLatLng: vi.fn(),
        getLatLng: () => ({ lat: 28.5921, lng: 77.0460 }),
        bindPopup: function() { return this; },
        on: vi.fn(),
      }),
      circle: () => ({
        addTo: function() { return this; },
        setRadius: vi.fn(),
        setLatLng: vi.fn(),
        setStyle: vi.fn(),
        remove: vi.fn(),
      }),
      divIcon: () => ({}),
    },
  };
});

describe('NIVAS Unified Chat: Document Intelligence & Neighborhood Advisor', () => {
  const mockLocation = {
    latitude: 28.5921,
    longitude: 77.0460,
    address: 'Dwarka Sector 12, South West Delhi, Delhi',
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(api, 'fetchLivabilityLocationData').mockResolvedValue({
      location: mockLocation,
      infrastructure: {
        status: 'active',
        schools_count: 5,
        hospitals_count: 2,
        facilities: [],
      },
      air_quality: {
        status: 'active',
        aqi_value: 120,
        category: 'Moderate',
      },
    });
  });

  it('Flow A: ordinary neighborhood query without attachments calls sendLivabilityChatMessage', async () => {
    vi.spyOn(api, 'sendLivabilityChatMessage').mockResolvedValue({
      reply: 'Dwarka Sector 12 has multiple schools and convenient metro connectivity.',
      sources: ['OpenStreetMap Overpass API'],
      is_ai_generated: false,
      provider_configured: false,
    });

    render(<LivabilityWorkspace location={mockLocation} initialChatOpen={true} />);

    const input = screen.getByPlaceholderText(/Ask about neighborhood livability/i);
    fireEvent.change(input, { target: { value: 'How is the metro connectivity?' } });

    const sendBtn = screen.getByLabelText('Send message');
    fireEvent.click(sendBtn);

    await waitFor(() => {
      expect(api.sendLivabilityChatMessage).toHaveBeenCalledTimes(1);
    });

    expect(screen.getByText(/How is the metro connectivity\?/i)).toBeTruthy();
    expect(screen.getByText(/Dwarka Sector 12 has multiple schools/i)).toBeTruthy();
  });

  it('Flow B: validates document files against size (>10MB) and format', async () => {
    render(<LivabilityWorkspace location={mockLocation} initialChatOpen={true} />);

    const fileInput = screen.getByTestId('chat-file-input');

    // 1. Oversized file (12MB)
    const bigFile = new File(['x'.repeat(100)], 'huge_deed.pdf', { type: 'application/pdf' });
    Object.defineProperty(bigFile, 'size', { value: 12 * 1024 * 1024 });

    fireEvent.change(fileInput, { target: { files: [bigFile] } });

    await waitFor(() => {
      expect(screen.getByTestId('chat-validation-errors')).toBeTruthy();
      expect(screen.getByText(/'huge_deed\.pdf' exceeds the 10MB limit/i)).toBeTruthy();
    });

    // 2. Unsupported format (.exe)
    const invalidFile = new File(['content'], 'virus.exe', { type: 'application/octet-stream' });
    fireEvent.change(fileInput, { target: { files: [invalidFile] } });

    await waitFor(() => {
      expect(screen.getByText(/'virus\.exe' has an unsupported file format/i)).toBeTruthy();
    });
  });

  it('Flow C: stages attachments in tray, allows removal, and attaches valid files', async () => {
    render(<LivabilityWorkspace location={mockLocation} initialChatOpen={true} />);

    const fileInput = screen.getByTestId('chat-file-input');
    const validFile = new File(['Sale Deed Text Content'], 'sale_deed_plot_42.txt', { type: 'text/plain' });

    fireEvent.change(fileInput, { target: { files: [validFile] } });

    await waitFor(() => {
      expect(screen.getByTestId('chat-attachments-tray')).toBeTruthy();
      expect(screen.getByText('sale_deed_plot_42.txt')).toBeTruthy();
    });

    // Remove the file chip
    const removeBtn = screen.getByLabelText('Remove sale_deed_plot_42.txt');
    fireEvent.click(removeBtn);

    await waitFor(() => {
      expect(screen.queryByTestId('chat-attachments-tray')).not.toBeTruthy();
    });
  });

  it('Flow D: single document upload and analysis renders DocumentChatCard with citations and updates active context', async () => {
    const mockAnalysisResult = {
      documents: [
        {
          document_id: 'doc-101',
          filename: 'delhi_dwarka_sale_deed.txt',
          file_size_bytes: 2048,
          page_count: 3,
          document_type: 'Sale Deed',
          document_type_confidence: 0.95,
          is_scanned_or_empty: false,
          warnings: [],
          parties: [
            {
              name: 'Rajesh Kumar Sharma',
              role: 'Vendor / Seller',
              details: 'Son of Shri M.L. Sharma',
              evidence: { page_number: 1, excerpt_text: 'RAJESH KUMAR SHARMA, hereinafter called the VENDOR', confidence: 0.9 },
            },
            {
              name: 'Priya Mehra',
              role: 'Purchaser / Buyer',
              details: 'Daughter of Shri A.K. Mehra',
              evidence: { page_number: 1, excerpt_text: 'PRIYA MEHRA, hereinafter called the PURCHASER', confidence: 0.9 },
            },
          ],
          property_details: {
            plot_survey_number: 'Plot No. 42, Pocket 1',
            khasra_number: '14/25',
            address: 'Sector 12, Dwarka, New Delhi 110078',
            evidence: { page_number: 2, excerpt_text: 'SCHEDULE: Plot No. 42, Pocket 1, Sector 12 Dwarka', confidence: 0.9 },
          },
          financials: {
            declared_consideration: '₹1,25,00,000',
            numeric_amount: 12500000,
            currency: 'INR',
            evidence: { page_number: 2, excerpt_text: 'total consideration of Rs. 1,25,00,000/-', confidence: 0.95 },
          },
          dates: {
            execution_date: '15th March 2024',
          },
          registration: {
            sub_registrar_office: 'Sub-Registrar IX (Kapashera / South West Delhi)',
            registration_number: 'IN-DL987654321',
          },
        },
      ],
      comparison: null,
      legal_disclaimer: 'NIVAS Document Intelligence provides automated informational text analysis for decision support only.',
      registry_verification_status: 'not_verified_live_registry_unavailable',
    };

    vi.spyOn(api, 'analyzeDocuments').mockResolvedValue(mockAnalysisResult);

    render(<LivabilityWorkspace location={mockLocation} initialChatOpen={true} />);

    // Attach file
    const fileInput = screen.getByTestId('chat-file-input');
    const validFile = new File(['Sale deed text content'], 'delhi_dwarka_sale_deed.txt', { type: 'text/plain' });
    fireEvent.change(fileInput, { target: { files: [validFile] } });

    // Send
    const sendBtn = screen.getByLabelText('Send message');
    fireEvent.click(sendBtn);

    await waitFor(() => {
      expect(api.analyzeDocuments).toHaveBeenCalledTimes(1);
    });

    // Check assistant response with DocumentChatCard
    await waitFor(() => {
      expect(screen.getByTestId('chat-doc-card')).toBeTruthy();
      expect(screen.getAllByText('delhi_dwarka_sale_deed.txt').length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText('Rajesh Kumar Sharma')).toBeTruthy();
      expect(screen.getByText('Priya Mehra')).toBeTruthy();
      expect(screen.getByText(/Plot No\. 42, Pocket 1/i)).toBeTruthy();
      expect(screen.getByText(/₹1,25,00,000/i)).toBeTruthy();
    });

    // Active documents pill strip should now be present
    expect(screen.getByTestId('chat-active-docs-bar')).toBeTruthy();
    expect(screen.getByTestId('chat-active-doc-badge')).toBeTruthy();
  });

  it('Flow E: follow-up questions on active documents resolve deterministically and with citations', async () => {
    const mockAnalysisResult = {
      documents: [
        {
          document_id: 'doc-101',
          filename: 'delhi_dwarka_sale_deed.txt',
          file_size_bytes: 2048,
          page_count: 3,
          document_type: 'Sale Deed',
          parties: [
            {
              name: 'Rajesh Kumar Sharma',
              role: 'Vendor',
              evidence: { page_number: 1, excerpt_text: 'RAJESH KUMAR SHARMA VENDOR', confidence: 0.9 },
            },
            {
              name: 'Priya Mehra',
              role: 'Purchaser',
              evidence: { page_number: 1, excerpt_text: 'PRIYA MEHRA PURCHASER', confidence: 0.9 },
            },
          ],
          property_details: {
            plot_survey_number: 'Plot No. 42',
            address: 'Dwarka Sector 12',
            evidence: { page_number: 2, excerpt_text: 'Plot No. 42 Dwarka', confidence: 0.9 },
          },
          financials: {
            declared_consideration: '₹1,25,00,000',
            numeric_amount: 12500000,
            evidence: { page_number: 2, excerpt_text: 'Rs. 1,25,00,000', confidence: 0.95 },
          },
          dates: { execution_date: '15 March 2024' },
          registration: { sub_registrar_office: 'SRO IX Kapashera' },
        },
      ],
      comparison: null,
      legal_disclaimer: 'Informational decision support only.',
    };

    vi.spyOn(api, 'analyzeDocuments').mockResolvedValue(mockAnalysisResult);

    render(<LivabilityWorkspace location={mockLocation} initialChatOpen={true} />);

    // Step 1: Upload document
    const fileInput = screen.getByTestId('chat-file-input');
    const validFile = new File(['text'], 'delhi_dwarka_sale_deed.txt', { type: 'text/plain' });
    fireEvent.change(fileInput, { target: { files: [validFile] } });
    fireEvent.click(screen.getByLabelText('Send message'));

    await waitFor(() => {
      expect(screen.getByTestId('chat-active-docs-bar')).toBeTruthy();
    });

    // Step 2: Follow-up query about parties
    const chatInput = screen.getByPlaceholderText(/Ask about delhi_dwarka_sale_deed\.txt/i);
    fireEvent.change(chatInput, { target: { value: 'Who is the buyer and who is the seller?' } });
    fireEvent.click(screen.getByLabelText('Send message'));

    await waitFor(() => {
      expect(screen.getByText(/Here are the parties explicitly extracted from/i)).toBeTruthy();
      expect(screen.getAllByText(/Rajesh Kumar Sharma/i).length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText(/Page 1/i).length).toBeGreaterThanOrEqual(1);
    });

    // Step 3: Follow-up query about consideration
    fireEvent.change(chatInput, { target: { value: 'What is the declared sale consideration amount?' } });
    fireEvent.click(screen.getByLabelText('Send message'));

    await waitFor(() => {
      expect(screen.getByText(/Financial terms extracted/i)).toBeTruthy();
      expect(screen.getAllByText(/₹1,25,00,000/i).length).toBeGreaterThanOrEqual(1);
    });

    // Step 4: Clear active documents
    const clearBtn = screen.getByTestId('chat-clear-active-docs-btn');
    fireEvent.click(clearBtn);

    await waitFor(() => {
      expect(screen.queryByTestId('chat-active-docs-bar')).not.toBeTruthy();
    });
  });

  it('Flow F: preserves staged files and chat input when upload fails', async () => {
    vi.spyOn(api, 'analyzeDocuments').mockRejectedValue({
      response: { data: { detail: 'Network gateway timeout reading PDF stream' } },
    });

    render(<LivabilityWorkspace location={mockLocation} initialChatOpen={true} />);

    const fileInput = screen.getByTestId('chat-file-input');
    const validFile = new File(['content'], 'sample_deed.pdf', { type: 'application/pdf' });
    fireEvent.change(fileInput, { target: { files: [validFile] } });

    const chatInput = screen.getByPlaceholderText(/Ask questions about 1 attached document/i);
    fireEvent.change(chatInput, { target: { value: 'Verify seller name in this deed' } });

    fireEvent.click(screen.getByLabelText('Send message'));

    await waitFor(() => {
      expect(screen.getByText(/Document analysis failed: Network gateway timeout/i)).toBeTruthy();
    });

    // Staged files should be preserved so user does not lose work
    await waitFor(() => {
      expect(screen.getByTestId('chat-attachments-tray')).toBeTruthy();
      expect(screen.getByText('sample_deed.pdf')).toBeTruthy();
      expect(screen.getByDisplayValue('Verify seller name in this deed')).toBeTruthy();
    });
  });

  it('Flow G: multi-document comparison renders cross-document discrepancy table in chat', async () => {
    const mockMultiResult = {
      documents: [
        {
          document_id: 'doc-1',
          filename: 'Agreement_To_Sell_2023.txt',
          document_type: 'Agreement to Sell',
          page_count: 2,
          parties: [{ name: 'Amit Verma', role: 'Vendor' }],
          property_details: { plot_survey_number: 'Plot 42' },
          financials: { numeric_amount: 11000000 },
        },
        {
          document_id: 'doc-2',
          filename: 'Sale_Deed_2024.txt',
          document_type: 'Sale Deed',
          page_count: 3,
          parties: [{ name: 'Amit Verma', role: 'Vendor' }],
          property_details: { plot_survey_number: 'Plot 42' },
          financials: { numeric_amount: 12500000 },
        },
      ],
      comparison: {
        total_documents_compared: 2,
        consistent_fields: ['plot_survey_number', 'vendor_name'],
        discrepancies: [
          {
            field_name: 'Consideration Amount',
            severity: 'high',
            status: 'mismatch',
            description: 'Consideration amount delta of ₹15,00,000 between Agreement to Sell and Sale Deed.',
            document_values: {
              'Agreement_To_Sell_2023.txt': '₹1,10,00,000',
              'Sale_Deed_2024.txt': '₹1,25,00,000',
            },
            recommendation: 'Verify payment receipts and TDS Form 26QB for consideration difference.',
          },
        ],
      },
      legal_disclaimer: 'Informational decision support only.',
    };

    vi.spyOn(api, 'analyzeDocuments').mockResolvedValue(mockMultiResult);

    render(<LivabilityWorkspace location={mockLocation} initialChatOpen={true} />);

    const fileInput = screen.getByTestId('chat-file-input');
    const f1 = new File(['text 1'], 'Agreement_To_Sell_2023.txt', { type: 'text/plain' });
    const f2 = new File(['text 2'], 'Sale_Deed_2024.txt', { type: 'text/plain' });

    fireEvent.change(fileInput, { target: { files: [f1, f2] } });
    fireEvent.click(screen.getByLabelText('Send message'));

    await waitFor(() => {
      expect(screen.getByTestId('chat-discrepancy-card')).toBeTruthy();
      expect(screen.getByText('HIGH SEVERITY')).toBeTruthy();
      expect(screen.getByText(/Consideration amount delta of ₹15,00,000/i)).toBeTruthy();
    });
  });

  it('Flow H: DocumentIntelligenceWorkspace bridge button invokes onOpenInChat with files', async () => {
    const mockOnOpenInChat = vi.fn();
    render(<DocumentIntelligenceWorkspace onOpenInChat={mockOnOpenInChat} />);

    // Top bridge banner
    const bridgeBtn = screen.getByTestId('doc-bridge-to-chat-btn');
    expect(bridgeBtn).toBeTruthy();

    fireEvent.click(bridgeBtn);
    expect(mockOnOpenInChat).toHaveBeenCalledTimes(1);
    expect(mockOnOpenInChat).toHaveBeenCalledWith([]);
  });
});
