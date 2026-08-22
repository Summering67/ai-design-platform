interface FlexContainer {
    direction: 'row' | 'column';
    justifyContent: 'flex-start' | 'flex-end' | 'center' | 'space-between' | 'space-around';    
    alignItems: 'flex-start' | 'flex-end' | 'center' | 'stretch' | 'baseline';
    gap: number;
    padding: number;
    width: number;
    height: number;
    children: FlexItem[];
}

interface FlexItem {
    flex: number;
    alignSelf: 'auto' | 'flex-start' | 'flex-end' | 'center';
    margin:[number, number, number, number]; // top, right, bottom, left
    width?: number;
    height?: number;
}

class AutolayoutEngine {
    // 核心Flex布局计算方法
    calculateLayout(container: FlexContainer): FlexContainer {
        const { direction, justifyContent, alignItems, gap, padding, width, height, children } = container;
        const availableWidth = width - padding * 2 ;
        const availableHeight = height - padding * 2;

        // 计算子元素总基础尺寸
        let totalFlexGrow = children.reduce((sum, child) => sum + (child.flex || 0), 0);
        let totalFixedSize = children.reduce((sum, child) => sum + (direction === 'row' ? (child.width || 0) : (child.height || 0)), 0);
        let totalGapSize = gap * (children.length - 1);

        // 分配剩余空间给flex子元素
        const remianingSize = direction === 'row' 
        ? availableWidth - totalFixedSize - totalGapSize 
        : availableHeight - totalFixedSize - totalGapSize;

        const flexUnitSize = totalFlexGrow > 0 ? remianingSize / totalFlexGrow : 0;
        
        // 计算每个子元素的最终尺寸和位置
        let currentOffset = padding;
        const updatedChildren = children.map(child => {
            const childSize = direction === 'row' 
                ? (child.width || 0) + (child.flex || 0) * flexUnitSize 
                : (child.height || 0) + (child.flex || 0) * flexUnitSize;

            const position = {
                x: direction === 'row' ? currentOffset : padding,
                y: direction === 'column' ? currentOffset : padding
            };
            currentOffset += childSize + gap;
            return { ...child, calculatedSize: childSize, caculatedPosition: position};
        });
        return { ...container, children: updatedChildren };
    }

    validateDesignSystem(schema: any): {valid: boolean; correctedSchema: any} {
        let corrected = JSON.parse(JSON.stringify(schema)); 
        let valid = true;

        // 校验间距是否为8px倍数
        if (corrected.style_layer?.global?.grid_unit !== '8px') {
            corrected.style_layer.global.grid_unit = '8px';
            valid = false; 

        }

        // 校验颜色是否符合设计系统
        if (corrected.style_layer?.global?.color_palette !== 'design_system_palette') {
            corrected.style_layer.global.color_palette = 'design_system_palette';
            valid = false; 
        }

        return { valid, correctedSchema: corrected };
    }
}