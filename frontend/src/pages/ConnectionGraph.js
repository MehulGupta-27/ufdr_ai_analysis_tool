import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { Network, Users, MessageCircle, Phone, AlertCircle, Loader, Search, Filter } from 'lucide-react';
import axios from 'axios';
import './ConnectionGraph.css';

const ConnectionGraph = ({ currentCase }) => {
  const [graphData, setGraphData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedNode, setSelectedNode] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [filteredNodes, setFilteredNodes] = useState([]);
  const [loadedCases, setLoadedCases] = useState(new Set()); // Track loaded cases
  const svgRef = useRef(null);

  // Memoize the current case number to prevent unnecessary re-renders
  const currentCaseNumber = useMemo(() => currentCase?.case_number, [currentCase?.case_number]);

  const fetchConnectionGraph = useCallback(async (forceRefresh = false) => {
    if (!currentCaseNumber) return;

    // Check if we already have data for this case and it's not a forced refresh
    if (!forceRefresh && loadedCases.has(currentCaseNumber) && graphData) {
      console.log(`📋 Using cached graph data for case: ${currentCaseNumber}`);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      console.log(`🔍 Fetching connection graph for case: ${currentCaseNumber}${forceRefresh ? ' (forced refresh)' : ''}`);
      const response = await axios.get(`/api/v1/graph/network/${currentCaseNumber}`);
      
      console.log('📊 Graph API response:', response.data);
      
      // Check for specific error types
      if (response.data.error === 'neo4j_connection_failed' || response.data.error === 'neo4j_connection_test_failed') {
        setError('Neo4j database is not available. Please ensure Neo4j is running in Docker Compose.');
        setLoadedCases(prev => new Set([...prev, currentCaseNumber]));
        return;
      }
      
      if (response.data.network && response.data.network.length > 0) {
        const processedData = processGraphData(response.data.network);
        console.log('📈 Processed graph data:', processedData);
        setGraphData(processedData);
        setFilteredNodes(processedData.nodes);
        // Mark this case as loaded
        setLoadedCases(prev => new Set([...prev, currentCaseNumber]));
      } else {
        const message = response.data.message || 'No network data found for this case';
        console.log('⚠️ No network data:', message);
        
        // Try to create a basic graph from contacts if available
        if (response.data.total_nodes > 0) {
          console.log('🔄 Attempting to create basic graph from contacts...');
          const basicGraph = await createBasicGraphFromContacts(currentCaseNumber);
          if (basicGraph.nodes.length > 0) {
            setGraphData(basicGraph);
            setFilteredNodes(basicGraph.nodes);
            setLoadedCases(prev => new Set([...prev, currentCaseNumber]));
            return;
          }
        }
        
        setError(message);
        // Mark this case as loaded even if no data
        setLoadedCases(prev => new Set([...prev, currentCaseNumber]));
      }
    } catch (err) {
      console.error('❌ Error fetching connection graph:', err);
      const errorMessage = err.response?.data?.detail || err.response?.data?.message || 'Failed to load connection graph';
      setError(errorMessage);
      // Mark this case as loaded even on error to prevent retries
      setLoadedCases(prev => new Set([...prev, currentCaseNumber]));
    } finally {
      setLoading(false);
    }
  }, [currentCaseNumber, loadedCases]); // Remove graphData from dependencies to avoid circular dependency

  const createBasicGraphFromContacts = useCallback(async (caseNumber) => {
    try {
      // Try to get contacts from the case
      const response = await axios.get(`/api/v1/case/${caseNumber}/counts`);
      if (response.data.success && response.data.counts.contacts > 0) {
        // Create basic nodes from contacts
        const nodes = [];
        for (let i = 0; i < Math.min(response.data.counts.contacts, 10); i++) {
          nodes.push({
            id: `contact_${i}`,
            name: `Contact ${i + 1}`,
            phone_number: `+XXX-XXX-XXXX`,
            type: 'person',
            connections: 0
          });
        }
        return { nodes, links: [] };
      }
    } catch (error) {
      console.log('Could not create basic graph:', error);
    }
    return { nodes: [], links: [] };
  }, []);

  // useEffect hooks after all functions are defined
  useEffect(() => {
    if (currentCaseNumber && !loadedCases.has(currentCaseNumber)) {
      console.log(`🔄 Loading connection graph for case: ${currentCaseNumber}`);
      fetchConnectionGraph();
    }
  }, [currentCaseNumber, fetchConnectionGraph]);

  // Clear graph data when switching to a different case
  useEffect(() => {
    if (currentCaseNumber && !loadedCases.has(currentCaseNumber)) {
      // Clear previous case data when switching to a new case
      setGraphData(null);
      setFilteredNodes([]);
      setSelectedNode(null);
      setError(null);
    }
  }, [currentCaseNumber, loadedCases]);

  useEffect(() => {
    if (graphData && searchTerm) {
      const filtered = graphData.nodes.filter(node => 
        node.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        node.phone_number.toLowerCase().includes(searchTerm.toLowerCase())
      );
      setFilteredNodes(filtered);
    } else {
      setFilteredNodes(graphData?.nodes || []);
    }
  }, [graphData, searchTerm]);

  const processGraphData = useCallback((networkData) => {
    console.log('🔄 Processing network data:', networkData);
    const nodes = [];
    const links = [];
    const nodeMap = new Map();

    // Process nodes (persons)
    networkData.forEach((item, index) => {
      // Handle p1 (source person)
      if (item.p1) {
        const nodeId = item.p1.id || item.p1.phone_number || `node_${index}_1`;
        if (!nodeMap.has(nodeId)) {
          nodes.push({
            id: nodeId,
            name: item.p1.name || item.p1.phone_number || 'Unknown',
            phone_number: item.p1.phone_number || 'Unknown',
            type: 'person',
            connections: 0
          });
          nodeMap.set(nodeId, nodes.length - 1);
        }
      }

      // Handle p2 (target person)
      if (item.p2) {
        const nodeId = item.p2.id || item.p2.phone_number || `node_${index}_2`;
        if (!nodeMap.has(nodeId)) {
          nodes.push({
            id: nodeId,
            name: item.p2.name || item.p2.phone_number || 'Unknown',
            phone_number: item.p2.phone_number || 'Unknown',
            type: 'person',
            connections: 0
          });
          nodeMap.set(nodeId, nodes.length - 1);
        }
      }

      // Process relationships
      if (item.r && item.p1 && item.p2) {
        const sourceId = item.p1.id || item.p1.phone_number || `node_${index}_1`;
        const targetId = item.p2.id || item.p2.phone_number || `node_${index}_2`;
        
        links.push({
          source: sourceId,
          target: targetId,
          type: item.r.type || 'COMMUNICATES_WITH',
          frequency: item.r.frequency || 1,
          strength: item.r.communication_strength || 0.5,
          message_count: item.r.message_count || 0,
          call_count: item.r.call_count || 0
        });

        // Update connection counts
        const sourceIndex = nodeMap.get(sourceId);
        const targetIndex = nodeMap.get(targetId);
        if (sourceIndex !== undefined) nodes[sourceIndex].connections++;
        if (targetIndex !== undefined) nodes[targetIndex].connections++;
      }
    });

    console.log('📊 Processed result:', { nodes: nodes.length, links: links.length });
    return { nodes, links };
  }, []);

  const handleNodeClick = useCallback((node) => {
    console.log(`🖱️ Node clicked: ${node.name} (${node.id})`);
    setSelectedNode(node);
  }, []);

  const renderGraph = useCallback(() => {
    if (!graphData || !svgRef.current) return;

    const svg = svgRef.current;
    const containerRect = svg.getBoundingClientRect();
    const width = containerRect.width || 800;
    const height = containerRect.height || 600;
    
    // Clear previous content
    svg.innerHTML = '';

    // Set proper viewBox to ensure content fits
    svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
    svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');

    // Calculate layout with proper margins
    const margin = 80; // Increased margin to prevent cutoff
    const layoutWidth = width - (margin * 2);
    const layoutHeight = height - (margin * 2);

    // Improved force-directed layout simulation
    const nodes = filteredNodes.map((node, index) => {
      // Start with a circular layout for better distribution
      const angle = (index / filteredNodes.length) * 2 * Math.PI;
      const radius = Math.min(layoutWidth, layoutHeight) * 0.3;
      const centerX = width / 2;
      const centerY = height / 2;
      
      return {
        ...node,
        x: centerX + radius * Math.cos(angle) + (Math.random() - 0.5) * 50,
        y: centerY + radius * Math.sin(angle) + (Math.random() - 0.5) * 50,
        vx: 0,
        vy: 0
      };
    });

    // Ensure nodes stay within bounds
    nodes.forEach(node => {
      node.x = Math.max(margin, Math.min(width - margin, node.x));
      node.y = Math.max(margin, Math.min(height - margin, node.y));
    });

    const links = graphData.links.filter(link => 
      nodes.some(n => n.id === link.source) && 
      nodes.some(n => n.id === link.target)
    );

    // Render links first (behind nodes)
    links.forEach(link => {
      const sourceNode = nodes.find(n => n.id === link.source);
      const targetNode = nodes.find(n => n.id === link.target);
      
      if (sourceNode && targetNode) {
        const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        line.setAttribute('x1', sourceNode.x);
        line.setAttribute('y1', sourceNode.y);
        line.setAttribute('x2', targetNode.x);
        line.setAttribute('y2', targetNode.y);
        line.setAttribute('stroke', '#6366f1');
        line.setAttribute('stroke-width', Math.max(1, link.strength * 3));
        line.setAttribute('opacity', 0.6);
        line.setAttribute('class', 'connection-line');
        line.setAttribute('data-strength', link.strength);
        line.setAttribute('data-frequency', link.frequency);
        
        svg.appendChild(line);
      }
    });

    // Render nodes
    nodes.forEach(node => {
      const group = document.createElementNS('http://www.w3.org/2000/svg', 'g');
      group.setAttribute('class', 'node-group');
      group.setAttribute('data-node-id', node.id);

      const radius = Math.max(15, Math.min(30, 15 + node.connections * 2));
      
      const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      circle.setAttribute('cx', node.x);
      circle.setAttribute('cy', node.y);
      circle.setAttribute('r', radius);
      circle.setAttribute('fill', node.connections > 5 ? '#ef4444' : node.connections > 2 ? '#f59e0b' : '#10b981');
      circle.setAttribute('stroke', '#ffffff');
      circle.setAttribute('stroke-width', '2');
      circle.setAttribute('class', 'node-circle');
      circle.setAttribute('data-connections', node.connections);

      const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      text.setAttribute('x', node.x);
      text.setAttribute('y', node.y + 5);
      text.setAttribute('text-anchor', 'middle');
      text.setAttribute('fill', '#ffffff');
      text.setAttribute('font-size', '12');
      text.setAttribute('font-weight', 'bold');
      text.setAttribute('class', 'node-label');
      
      // Truncate text based on available space
      const maxTextLength = Math.floor(radius / 3);
      text.textContent = node.name.length > maxTextLength ? 
        node.name.substring(0, maxTextLength) + '...' : node.name;

      group.appendChild(circle);
      group.appendChild(text);
      svg.appendChild(group);

      // Add click event
      group.addEventListener('click', () => handleNodeClick(node));
    });
  }, [graphData, filteredNodes, handleNodeClick]);

  const clearGraphCache = useCallback(() => {
    console.log(`🗑️ Clearing graph cache for case: ${currentCaseNumber}`);
    setGraphData(null);
    setFilteredNodes([]);
    setSelectedNode(null);
    setError(null);
    setLoadedCases(prev => {
      const newSet = new Set(prev);
      newSet.delete(currentCaseNumber);
      return newSet;
    });
  }, [currentCaseNumber]);

  const handleRefreshGraph = useCallback(() => {
    console.log(`🔄 Manual refresh requested for case: ${currentCaseNumber}`);
    fetchConnectionGraph(true);
  }, [currentCaseNumber, fetchConnectionGraph]);

  useEffect(() => {
    if (graphData) {
      renderGraph();
    }
  }, [renderGraph]);

  // Handle window resize to re-render graph
  useEffect(() => {
    const handleResize = () => {
      if (graphData) {
        // Small delay to ensure container has updated dimensions
        setTimeout(() => {
          renderGraph();
        }, 100);
      }
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [graphData, renderGraph]);

  const getConnectionDetails = useCallback((nodeId) => {
    if (!graphData) return [];
    
    return graphData.links
      .filter(link => link.source === nodeId || link.target === nodeId)
      .map(link => {
        const otherNodeId = link.source === nodeId ? link.target : link.source;
        const otherNode = graphData.nodes.find(n => n.id === otherNodeId);
        return {
          ...link,
          otherNode: otherNode || { name: 'Unknown', phone_number: 'Unknown' }
        };
      });
  }, [graphData]);

  if (!currentCase) {
    return (
      <div className="connection-graph-page">
        <div className="no-case-message">
          <Network size={64} className="no-case-icon" />
          <h2>No Case Selected</h2>
          <p>Please upload a UFDR file first to view connection graphs.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="connection-graph-page">
      <div className="graph-header">
        <div className="header-info">
          <Network className="header-icon" />
          <div>
            <h1>Connection Graph</h1>
            <p>Communication network for case {currentCase.case_number}</p>
            {loadedCases.has(currentCaseNumber) && graphData && (
              <div className="cache-status">
                <span className="cache-indicator">📋 Data cached</span>
                <span className="cache-info">({graphData.nodes.length} contacts, {graphData.links.length} connections)</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {error && (
        <div className="alert alert-error">
          <AlertCircle size={20} />
          {error}
        </div>
      )}

      <div className="graph-controls">
        <div className="search-container">
          <Search size={16} className="search-icon" />
          <input
            type="text"
            placeholder="Search contacts..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="search-input"
          />
        </div>
        
        <div className="button-group">
          <button 
            className="btn btn-secondary"
            onClick={handleRefreshGraph}
            disabled={loading}
          >
            {loading ? (
              <>
                <Loader className="loading-spinner" size={16} />
                Loading...
              </>
            ) : (
              <>
                <Network size={16} />
                Refresh Graph
              </>
            )}
          </button>
          
          {process.env.NODE_ENV === 'development' && (
            <button 
              className="btn btn-secondary"
              onClick={clearGraphCache}
              disabled={loading}
              title="Clear cache (dev only)"
            >
              <Filter size={16} />
              Clear Cache
            </button>
          )}
        </div>
      </div>

      <div className="graph-container">
        <div className="graph-visualization">
          <svg 
            ref={svgRef}
            className="connection-svg"
          >
            {/* SVG content will be rendered here */}
          </svg>
        </div>

        <div className="graph-sidebar">
          <div className="graph-stats">
            <h3>Network Statistics</h3>
            {graphData && (
              <div className="stats-grid">
                <div className="stat-item">
                  <Users size={20} />
                  <div>
                    <span className="stat-number">{graphData.nodes.length}</span>
                    <span className="stat-label">Total Contacts</span>
                  </div>
                </div>
                <div className="stat-item">
                  <MessageCircle size={20} />
                  <div>
                    <span className="stat-number">{graphData.links.length}</span>
                    <span className="stat-label">Connections</span>
                  </div>
                </div>
                <div className="stat-item">
                  <Network size={20} />
                  <div>
                    <span className="stat-number">
                      {graphData.nodes.length > 0 ? 
                        (graphData.links.length / graphData.nodes.length).toFixed(1) : 0
                      }
                    </span>
                    <span className="stat-label">Avg Connections</span>
                  </div>
                </div>
              </div>
            )}
          </div>

          {selectedNode && (
            <div className="node-details">
              <h3>Contact Details</h3>
              <div className="contact-info">
                <div className="contact-name">{selectedNode.name}</div>
                <div className="contact-phone">{selectedNode.phone_number}</div>
                <div className="contact-connections">
                  {selectedNode.connections} connections
                </div>
              </div>

              <div className="connections-list">
                <h4>Direct Connections</h4>
                {getConnectionDetails(selectedNode.id).map((connection, index) => (
                  <div key={index} className="connection-item">
                    <div className="connection-contact">
                      <strong>{connection.otherNode.name}</strong>
                      <span className="connection-phone">{connection.otherNode.phone_number}</span>
                    </div>
                    <div className="connection-metrics">
                      <div className="metric">
                        <MessageCircle size={14} />
                        {connection.message_count} messages
                      </div>
                      <div className="metric">
                        <Phone size={14} />
                        {connection.call_count} calls
                      </div>
                      <div className="metric">
                        <Network size={14} />
                        {connection.frequency} total
                      </div>
                    </div>
                    <div className="connection-strength">
                      <div 
                        className="strength-bar"
                        style={{ width: `${connection.strength * 100}%` }}
                      ></div>
                      <span>Strength: {(connection.strength * 100).toFixed(0)}%</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {!selectedNode && graphData && (
            <div className="node-list">
              <h3>All Contacts</h3>
              <div className="contacts-list">
                {filteredNodes
                  .sort((a, b) => b.connections - a.connections)
                  .map((node, index) => (
                    <div 
                      key={node.id}
                      className={`contact-item ${selectedNode?.id === node.id ? 'selected' : ''}`}
                      onClick={() => handleNodeClick(node)}
                    >
                      <div className="contact-avatar">
                        <Users size={16} />
                      </div>
                      <div className="contact-details">
                        <div className="contact-name">{node.name}</div>
                        <div className="contact-phone">{node.phone_number}</div>
                      </div>
                      <div className="contact-connections">
                        {node.connections}
                      </div>
                    </div>
                  ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ConnectionGraph;
