/**
 * NIVAS Document Intelligence Chat Integration Helper.
 * Provides file validation, intent routing, grounded follow-up answering,
 * and presentation synthesis for the unified Neighborhood AI Advisor.
 */

export const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024; // 10 MB limit
export const MAX_FILES_LIMIT = 10;
export const ALLOWED_EXTENSIONS = ['.pdf', '.txt', '.text', '.md', '.markdown', '.csv'];

export const LEGAL_DISCLAIMER_TEXT =
  'NIVAS Document Intelligence provides automated informational text analysis and cross-referencing for decision support only. It does NOT constitute a legal title opinion, property ownership verification, or official registration check. Official land registry records (Sub-Registrar / Land Revenue Office) and consultation with a qualified advocate or title legal professional are required for definitive legal verification. Live Sub-Registrar database verification is currently unavailable.';

/**
 * Format bytes into human-readable string.
 */
export function formatFileSize(bytes) {
  if (typeof bytes !== 'number' || isNaN(bytes) || bytes <= 0) return '0 B';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

/**
 * Validates selected document files before upload.
 */
export function validateDocumentFiles(files, currentFilesCount = 0) {
  const validFiles = [];
  const errors = [];

  const fileList = Array.from(files || []);

  if (currentFilesCount + fileList.length > MAX_FILES_LIMIT) {
    errors.push(`Maximum ${MAX_FILES_LIMIT} documents can be attached simultaneously.`);
    return { validFiles, errors };
  }

  fileList.forEach((file) => {
    const filename = file.name || 'unnamed_file';
    const lowerName = filename.toLowerCase();

    // Check size
    if (file.size > MAX_FILE_SIZE_BYTES) {
      errors.push(`'${filename}' exceeds the 10MB limit (${formatFileSize(file.size)}).`);
      return;
    }

    if (file.size === 0) {
      errors.push(`'${filename}' is empty (0 bytes).`);
      return;
    }

    // Check extension
    const hasValidExt = ALLOWED_EXTENSIONS.some((ext) => lowerName.endsWith(ext));
    if (!hasValidExt) {
      errors.push(
        `'${filename}' has an unsupported file format. Please upload a PDF, TXT, or Markdown document.`
      );
      return;
    }

    validFiles.push(file);
  });

  return { validFiles, errors };
}

/**
 * Determines whether the user query is intended for neighborhood/civic livability telemetry.
 */
export function isNeighborhoodQuery(query) {
  if (!query || typeof query !== 'string') return false;
  const q = query.toLowerCase();
  return (
    q.includes('school') ||
    q.includes('hospital') ||
    q.includes('clinic') ||
    q.includes('pharmacy') ||
    q.includes('metro') ||
    q.includes('transit') ||
    q.includes('station') ||
    q.includes('bus') ||
    q.includes('aqi') ||
    q.includes('air quality') ||
    q.includes('pollution') ||
    q.includes('crime') ||
    q.includes('safety') ||
    q.includes('flood') ||
    q.includes('waterlog') ||
    q.includes('distance') ||
    q.includes('how far') ||
    q.includes('amenit') ||
    q.includes('infrastructure')
  );
}

/**
 * Evaluates whether a query relates to document intelligence or active documents.
 */
export function isDocumentQuery(query, hasAttachedFiles, activeDocsCount) {
  if (hasAttachedFiles) return true;
  if (activeDocsCount === 0) return false;
  if (!query || typeof query !== 'string') return false;

  const q = query.toLowerCase();
  return (
    q.includes('deed') ||
    q.includes('document') ||
    q.includes('agreement') ||
    q.includes('contract') ||
    q.includes('party') ||
    q.includes('parties') ||
    q.includes('buyer') ||
    q.includes('seller') ||
    q.includes('vendor') ||
    q.includes('purchaser') ||
    q.includes('consideration') ||
    q.includes('price') ||
    q.includes('amount') ||
    q.includes('cost') ||
    q.includes('stamp duty') ||
    q.includes('registration') ||
    q.includes('plot') ||
    q.includes('survey') ||
    q.includes('khasra') ||
    q.includes('schedule') ||
    q.includes('boundar') ||
    q.includes('discrepan') ||
    q.includes('compare') ||
    q.includes('inconsisten') ||
    q.includes('conflict') ||
    q.includes('evidence') ||
    q.includes('citation') ||
    q.includes('page') ||
    q.includes('clause') ||
    q.includes('lawyer') ||
    q.includes('advocate') ||
    q.includes('verify') ||
    q.includes('verification') ||
    q.includes('summar') ||
    q.includes('location') ||
    q.includes('match')
  );
}

/**
 * Generate a grounded conversational answer for follow-up questions on active documents.
 */
export function generateDocumentFollowUpReply(query, activeDocuments, selectedLocation) {
  if (!activeDocuments || activeDocuments.length === 0) {
    return {
      text: 'No documents are currently active in context. Please attach a deed or contract using the paperclip icon to analyze legal clauses.',
      sources: ['NIVAS Document Intelligence'],
    };
  }

  const q = (query || '').toLowerCase();
  const doc = activeDocuments[0]; // primary active doc
  const docCount = activeDocuments.length;
  const isMulti = docCount > 1;

  // 1. Parties Query (buyer, seller, vendor, purchaser, party)
  if (/buyer|seller|vendor|purchaser|party|parties|names?|who (is|are)/.test(q)) {
    const partySections = activeDocuments.map((d) => {
      if (!d.parties || d.parties.length === 0) {
        return `**${d.filename}** (${d.document_type}): No parties were explicitly identified in extracted text.`;
      }
      const pList = d.parties
        .map((p) => {
          const cite = p.evidence?.page_number ? ` (Cited: Page ${p.evidence.page_number})` : '';
          const details = p.details ? ` — *${p.details}*` : '';
          return `• **${p.name}** [Role: ${p.role}]${details}${cite}`;
        })
        .join('\n');
      return `**${d.filename}** (${d.document_type}):\n${pList}`;
    });

    return {
      text: `Here are the parties explicitly extracted from ${isMulti ? 'the active documents' : `**${doc.filename}**`}:\n\n${partySections.join('\n\n')}\n\n*All party roles and citations reflect explicitly stated text in the uploaded document. Title authenticity must be verified at the relevant Sub-Registrar Office.*`,
      sources: ['NIVAS Document Intelligence', 'Extracted Legal Clauses'],
      evidenceList: activeDocuments.flatMap((d) => d.parties.map((p) => p.evidence).filter(Boolean)),
    };
  }

  // 2. Financials / Consideration Query
  if (/consideration|amount|price|cost|money|value|stamp duty|registration fee|rupees|inr|how much/.test(q)) {
    const finSections = activeDocuments.map((d) => {
      const f = d.financials || {};
      const amt = f.numeric_amount
        ? `₹${Number(f.numeric_amount).toLocaleString('en-IN')}`
        : f.declared_consideration || 'Not explicitly stated';
      const cite = f.evidence?.page_number ? ` (Cited: Page ${f.evidence.page_number})` : '';
      const stamp = f.stamp_duty ? `\n• Stamp Duty: ${f.stamp_duty}` : '';
      const regFee = f.registration_fee ? `\n• Registration Fee: ${f.registration_fee}` : '';
      return `**${d.filename}** (${d.document_type}):\n• Declared Consideration: **${amt}**${cite}${stamp}${regFee}`;
    });

    let extraNote = '';
    if (isMulti) {
      const amounts = activeDocuments.map((d) => ({
        name: d.filename,
        amt: d.financials?.numeric_amount,
      }));
      if (amounts[0].amt && amounts[1]?.amt && amounts[0].amt !== amounts[1].amt) {
        extraNote = `\n\n⚠️ **Financial Discrepancy Flag:** The consideration stated in ${amounts[0].name} (₹${amounts[0].amt.toLocaleString('en-IN')}) differs from ${amounts[1].name} (₹${amounts[1].amt.toLocaleString('en-IN')}). Verify payment receipts and bank clearance records with your legal counsel.`;
      }
    }

    return {
      text: `Financial terms extracted from ${isMulti ? 'the active documents' : `**${doc.filename}**`}:\n\n${finSections.join('\n\n')}${extraNote}`,
      sources: ['NIVAS Document Intelligence', 'Financial Clauses'],
      evidenceList: activeDocuments.map((d) => d.financials?.evidence).filter(Boolean),
    };
  }

  // 3. Property Details & Plot Number Query
  if (/plot|survey|khasra|schedule|address|area|sqft|boundar|property/.test(q)) {
    const propSections = activeDocuments.map((d) => {
      const p = d.property_details || {};
      const lines = [];
      if (p.plot_survey_number) lines.push(`• Plot / Survey No: **${p.plot_survey_number}**`);
      if (p.khasra_number) lines.push(`• Khasra No: **${p.khasra_number}**`);
      if (p.address) lines.push(`• Stated Address: **${p.address}**`);
      if (p.area_sqft) lines.push(`• Dimension / Area: **${p.area_sqft}**`);
      if (p.boundaries) {
        const b = p.boundaries;
        lines.push(`• Boundaries: North: ${b.north || 'N/A'}, South: ${b.south || 'N/A'}, East: ${b.east || 'N/A'}, West: ${b.west || 'N/A'}`);
      }
      const cite = p.evidence?.page_number ? `\n• Cited on: Page ${p.evidence.page_number}` : '';
      return `**${d.filename}** (${d.document_type}):\n${lines.length ? lines.join('\n') : '• Property schedule details not explicitly identified in extracted text.'}${cite}`;
    });

    return {
      text: `Property schedule extracted from ${isMulti ? 'the active documents' : `**${doc.filename}**`}:\n\n${propSections.join('\n\n')}\n\n*Verify physical plot boundaries and municipal zoning with a licensed surveyor before transaction completion.*`,
      sources: ['NIVAS Document Intelligence', 'Property Schedule'],
      evidenceList: activeDocuments.map((d) => d.property_details?.evidence).filter(Boolean),
    };
  }

  // 4. Dates & Registration Query
  if (/regist|sub-registrar|sro|date|execution|book|volume|jild/.test(q)) {
    const regSections = activeDocuments.map((d) => {
      const r = d.registration || {};
      const dt = d.dates || {};
      const lines = [];
      if (dt.execution_date) lines.push(`• Execution Date: **${dt.execution_date}**`);
      if (r.registration_date || dt.registration_date) {
        lines.push(`• Registration Date: **${r.registration_date || dt.registration_date}**`);
      }
      if (r.registration_number) lines.push(`• Registration No: **${r.registration_number}**`);
      if (r.sub_registrar_office) lines.push(`• Sub-Registrar Office: **${r.sub_registrar_office}**`);
      if (r.book_number || r.volume_number || r.page_range) {
        lines.push(`• Volume/Book Details: Book ${r.book_number || 'N/A'}, Vol ${r.volume_number || 'N/A'}, Pages ${r.page_range || 'N/A'}`);
      }
      const cite = r.evidence?.page_number ? `\n• Cited on: Page ${r.evidence.page_number}` : '';
      return `**${d.filename}** (${d.document_type}):\n${lines.length ? lines.join('\n') : '• Registration identifiers not explicitly stated or document is an unregistered draft/agreement.'}${cite}`;
    });

    return {
      text: `Registration and execution metadata extracted from ${isMulti ? 'the active documents' : `**${doc.filename}**`}:\n\n${regSections.join('\n\n')}\n\n*Live digital verification against the DORIS / Delhi e-Registration portal is required to confirm stamp validity.*`,
      sources: ['NIVAS Document Intelligence', 'Registration Metadata'],
      evidenceList: activeDocuments.flatMap((d) => [d.registration?.evidence, d.dates?.evidence]).filter(Boolean),
    };
  }

  // 5. Compare & Discrepancies Query
  if (/compare|discrepan|differ|inconsistent|conflict|match|mismatch/.test(q)) {
    if (!isMulti) {
      return {
        text: `Currently, only one document (**${doc.filename}**) is loaded in context. To perform cross-document consistency checks and detect discrepancies, please attach a second document (e.g. Prior Agreement, Conveyance, or Mother Deed) using the paperclip icon.`,
        sources: ['NIVAS Document Intelligence'],
      };
    }

    // Comparison summary across the 2 documents
    const docA = activeDocuments[0];
    const docB = activeDocuments[1];
    const compNotes = [];

    // Check plot
    const plotA = docA.property_details?.plot_survey_number;
    const plotB = docB.property_details?.plot_survey_number;
    if (plotA && plotB) {
      if (plotA.toLowerCase() === plotB.toLowerCase()) {
        compNotes.push(`✅ **Plot Number Match:** Both documents refer to Plot/Survey No: **${plotA}**.`);
      } else {
        compNotes.push(`⚠️ **Plot Number Mismatch:** ${docA.filename} cites **${plotA}**, whereas ${docB.filename} cites **${plotB}**.`);
      }
    }

    // Check consideration
    const numA = docA.financials?.numeric_amount;
    const numB = docB.financials?.numeric_amount;
    if (numA && numB) {
      if (numA === numB) {
        compNotes.push(`✅ **Consideration Match:** Stated transaction consideration matches at **₹${numA.toLocaleString('en-IN')}**.`);
      } else {
        compNotes.push(`⚠️ **Consideration Delta:** ₹${numA.toLocaleString('en-IN')} in ${docA.filename} vs ₹${numB.toLocaleString('en-IN')} in ${docB.filename} (Delta: ₹${Math.abs(numA - numB).toLocaleString('en-IN')}).`);
      }
    }

    // Check parties
    const vendorA = docA.parties?.find((p) => /vendor|seller/i.test(p.role))?.name;
    const vendorB = docB.parties?.find((p) => /vendor|seller/i.test(p.role))?.name;
    if (vendorA && vendorB) {
      if (vendorA.toLowerCase().includes(vendorB.toLowerCase()) || vendorB.toLowerCase().includes(vendorA.toLowerCase())) {
        compNotes.push(`✅ **Vendor Consistency:** Vendor identity (${vendorA}) is consistent across both documents.`);
      } else {
        compNotes.push(`⚠️ **Vendor Variance:** Vendor listed as **${vendorA}** in ${docA.filename} vs **${vendorB}** in ${docB.filename}. Verify title chain of transfer.`);
      }
    }

    return {
      text: `Cross-Document Comparison between **${docA.filename}** and **${docB.filename}**:\n\n${compNotes.join('\n\n')}\n\n*A textual discrepancy indicates a due-diligence inquiry point for your advocate, not definitive proof of legal defect or invalidity.*`,
      sources: ['NIVAS Document Intelligence Discrepancy Engine'],
    };
  }

  // 6. Lawyer / Legal Verification Advice Query
  if (/lawyer|advocate|verify|verification|check|due diligence|title opinion/.test(q)) {
    const sro = doc.registration?.sub_registrar_office || 'the concerned Sub-Registrar Office';
    const boundaries = doc.property_details?.boundaries ? 'verified against the physical schedule' : 'surveyed on-site';
    const plot = doc.property_details?.plot_survey_number || 'the subject property';

    return {
      text: `Key legal verification steps recommended for **${doc.filename}**:\n\n1. **Sub-Registrar Record Inspection:** Conduct a certified search of Book 1 records at **${sro}** for at least the past 30 years.\n2. **Encumbrance Certificate (EC):** Request Form 15/16 from the state registration department to confirm no active mortgages, court attachments, or liens exist on ${plot}.\n3. **Chain of Title:** Verify that original registered title deeds (Mother Deed, Conveyance, Allotment Letter) are in the seller's physical possession.\n4. **Physical Demarcation:** Ensure plot dimensions and boundary neighbors are ${boundaries}.\n5. **Circle Rate Compliance:** Cross-check declared consideration against official MCD / state circle rates to confirm full stamp duty clearance.\n\n*${LEGAL_DISCLAIMER_TEXT}*`,
      sources: ['NIVAS Legal Due Diligence Guidelines', 'Statutory Real Estate Verification'],
    };
  }

  // 7. Location Cross-Check Query
  if (/location|map|selected|neighborhood|dwarka|rohini|locality|near/.test(q)) {
    const docAddress = doc.property_details?.address || 'Not explicitly specified';
    const mapAddress = selectedLocation?.address || 'Map location not selected';

    return {
      text: `**Spatial Cross-Reference Analysis:**\n\n• **Property Location in Document:** ${docAddress}\n• **Exploration Focus on Map:** ${mapAddress}\n\n*Observation:* Verify that the Sub-Registrar Office having jurisdiction over **${docAddress}** matches the administrative district where the property physically resides. Cross-verifying document coordinates with municipal ward boundaries is recommended.`,
      sources: ['NIVAS Spatial Grounding & Document Intelligence'],
    };
  }

  // 8. Evidence & Citations Query
  if (/evidence|citation|page|excerpt|clause|quote|where/.test(q)) {
    const evidenceItems = [];
    activeDocuments.forEach((d) => {
      d.parties?.forEach((p) => {
        if (p.evidence) {
          evidenceItems.push(`• **${d.filename}** (Page ${p.evidence.page_number}): [Party: ${p.name}] "${p.evidence.excerpt_text}"`);
        }
      });
      if (d.financials?.evidence) {
        evidenceItems.push(`• **${d.filename}** (Page ${d.financials.evidence.page_number}): [Consideration] "${d.financials.evidence.excerpt_text}"`);
      }
      if (d.property_details?.evidence) {
        evidenceItems.push(`• **${d.filename}** (Page ${d.property_details.evidence.page_number}): [Property Schedule] "${d.property_details.evidence.excerpt_text}"`);
      }
      if (d.registration?.evidence) {
        evidenceItems.push(`• **${d.filename}** (Page ${d.registration.evidence.page_number}): [Registration] "${d.registration.evidence.excerpt_text}"`);
      }
    });

    return {
      text: `Here are the extracted evidence excerpts and page citations from active documents:\n\n${evidenceItems.slice(0, 6).join('\n\n')}\n\n*All citations refer to 1-indexed page positions in the digital file stream.*`,
      sources: ['NIVAS Grounded Citations Engine'],
    };
  }

  // 9. Summary / Overview Query
  if (/summar|overview|explain|tell me about|what is this/.test(q)) {
    const summaries = activeDocuments.map((d) => {
      const type = d.document_type || 'Legal Document';
      const pCount = d.page_count || 1;
      const parties = d.parties?.map((p) => `${p.name} (${p.role})`).join(', ') || 'Parties not extracted';
      const consideration = d.financials?.numeric_amount
        ? `₹${Number(d.financials.numeric_amount).toLocaleString('en-IN')}`
        : d.financials?.declared_consideration || 'Consideration not stated';
      const plot = d.property_details?.plot_survey_number || 'Plot number unstated';
      return `**${d.filename}** is classified as a **${type}** (${pCount} pages).\n• Parties: ${parties}\n• Stated Consideration: **${consideration}**\n• Plot / Property: **${plot}**`;
    });

    return {
      text: `Executive Summary of ${isMulti ? 'Active Documents' : `**${doc.filename}**`}:\n\n${summaries.join('\n\n')}\n\n*Ask specific questions about parties, consideration, evidence, or cross-document discrepancies at any time.*`,
      sources: ['NIVAS Document Intelligence'],
    };
  }

  // Default Fallback for document context
  return {
    text: `I have analyzed **${doc.filename}** (${doc.document_type}). You can ask me about:\n\n• **Parties**: "Who are the buyer and seller?"\n• **Financials**: "What is the declared consideration amount?"\n• **Property**: "What is the plot and survey number?"\n• **Registration**: "What is the registration date and SRO?"\n• **Evidence**: "Show me the cited excerpts and page numbers"\n• **Due Diligence**: "What should I verify with a property lawyer?"${isMulti ? '\n• **Comparison**: "Compare these deeds and identify discrepancies"' : ''}`,
    sources: ['NIVAS Document Intelligence'],
  };
}
